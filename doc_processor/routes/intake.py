"""
Intake Analysis Routes - Demonstrates modular Flask architecture

This blueprint handles all intake-related routes that were previously in the monolithic app.py.
Benefits:
- Smaller, focused files (easier to edit without indentation errors)
- Clear separation of concerns
- Better maintainability and testing
- Reduced merge conflicts in team development
"""

from flask import Blueprint, render_template, jsonify, request, Response, url_for
from ..document_detector import get_detector
from ..config_manager import app_config
from ..database import get_db_connection
from ..processing import database_connection
from ..batch_guard import get_or_create_intake_batch
from ..utils.path_utils import select_tmp_dir
import logging
import json
import os
from pathlib import Path
import time
import threading
import tempfile

# Create blueprint for intake routes
intake_bp = Blueprint('intake', __name__)


# use shared select_tmp_dir from utils.path_utils


def _resolve_working_pdf_path(original_filename: str) -> str:
    """Given an original intake filename (jpg/png/pdf), return the standardized/converted PDF path to use for analysis.

    Rules:
    - If original is an image (jpg/png/jpeg): use /tmp/{stem}_converted.pdf (perform conversion if missing)
    - If original is a PDF: prefer /tmp/{stem}_standardized.pdf if it exists; otherwise return the original PDF path
    """
    try:
        # PIL.Image is only conditionally used; import inside try and set to None if unavailable
        try:
            from PIL import Image
        except Exception:
            Image = None
    except Exception:
        Image = None

    orig_path = os.path.join(app_config.INTAKE_DIR, original_filename)
    stem = Path(original_filename).stem
    ext = Path(original_filename).suffix.lower()
    tmp_dir = select_tmp_dir()
    try:
        os.makedirs(tmp_dir, exist_ok=True)
    except Exception:
        pass

    # First, try to resolve from durable DB mapping if available
    mapped_path = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS intake_working_files (filename TEXT PRIMARY KEY, working_pdf TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        row = cur.execute("SELECT working_pdf FROM intake_working_files WHERE filename = ?", (original_filename,)).fetchone()
        if row:
            candidate = row[0]
            if candidate and os.path.exists(candidate):
                mapped_path = candidate
        conn.close()
    except Exception as db_err:
        logging.debug(f"intake_working_files lookup failed for {original_filename}: {db_err}")
        try:
            conn.close()
        except Exception:
            pass

    if mapped_path:
        return mapped_path

    if ext in {'.jpg', '.jpeg', '.png'}:
        converted = os.path.join(tmp_dir, f"{stem}_converted.pdf")
        if os.path.exists(converted):
            # Backfill mapping if missing
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS intake_working_files (filename TEXT PRIMARY KEY, working_pdf TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
                cur.execute("UPDATE intake_working_files SET working_pdf = ?, updated_at = CURRENT_TIMESTAMP WHERE filename = ?", (converted, original_filename))
                if cur.rowcount == 0:
                    cur.execute("INSERT INTO intake_working_files (filename, working_pdf) VALUES (?, ?)", (original_filename, converted))
                conn.commit()
                conn.close()
            except Exception as db_err:
                logging.debug(f"Failed to backfill mapping for {original_filename}: {db_err}")
                try:
                    conn.close()
                except Exception:
                    pass
            return converted
        # Convert on-demand if missing
        if Image is None:
            # Fallback: if conversion unavailable, use original (downstream viewers may still cope)
            return orig_path
        try:
            with Image.open(orig_path) as img:
                rgb = img.convert('RGB') if img.mode != 'RGB' else img
                rgb.save(converted, format='PDF')
            logging.info(f"On-demand conversion: {original_filename} -> {converted}")
            # Persist mapping
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS intake_working_files (filename TEXT PRIMARY KEY, working_pdf TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
                cur.execute("UPDATE intake_working_files SET working_pdf = ?, updated_at = CURRENT_TIMESTAMP WHERE filename = ?", (converted, original_filename))
                if cur.rowcount == 0:
                    cur.execute("INSERT INTO intake_working_files (filename, working_pdf) VALUES (?, ?)", (original_filename, converted))
                conn.commit()
                conn.close()
            except Exception as db_err:
                logging.debug(f"Failed to persist mapping for {original_filename}: {db_err}")
                try:
                    conn.close()
                except Exception:
                    pass
            return converted
        except Exception as e:
            logging.error(f"Failed to convert image to PDF for {original_filename}: {e}")
            return orig_path
    elif ext == '.pdf':
        standardized = os.path.join(tmp_dir, f"{stem}_standardized.pdf")
        path_to_use = standardized if os.path.exists(standardized) else orig_path
        # Persist or backfill mapping for PDFs too (so viewer and rescans use standardized when present)
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS intake_working_files (filename TEXT PRIMARY KEY, working_pdf TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            cur.execute("UPDATE intake_working_files SET working_pdf = ?, updated_at = CURRENT_TIMESTAMP WHERE filename = ?", (path_to_use, original_filename))
            if cur.rowcount == 0:
                cur.execute("INSERT INTO intake_working_files (filename, working_pdf) VALUES (?, ?)", (original_filename, path_to_use))
            conn.commit()
            conn.close()
        except Exception as db_err:
            logging.debug(f"Failed to persist mapping for PDF {original_filename}: {db_err}")
            try:
                conn.close()
            except Exception:
                pass
        return path_to_use
    else:
        # Unknown type, return original
        return orig_path


def background_analysis_worker(intake_dir, cache_file, batch_id=None):
    """Module-level background worker that performs analysis and writes cache atomically."""
    try:
        logging.info(f"Background analysis worker starting for {intake_dir}")
        detector = get_detector(use_llm_for_ambiguous=True)
        analyses = None
        # Prefer high-level batch analysis if detector supports it
        try:
            if hasattr(detector, 'analyze_intake_directory'):
                analyses = detector.analyze_intake_directory(intake_dir)
            else:
                # Fallback: analyze files one-by-one using analyze_pdf
                analyses = []
                try:
                    entries = os.listdir(intake_dir)
                except Exception:
                    entries = []
                for fname in sorted(entries):
                    lower = fname.lower()
                    if not lower.endswith(('.pdf', '.png', '.jpg', '.jpeg')):
                        continue
                    # Resolve a working PDF path for images and PDFs
                    try:
                        working = _resolve_working_pdf_path(fname)
                    except Exception:
                        working = os.path.join(intake_dir, fname)
                    try:
                        if hasattr(detector, 'analyze_pdf'):
                            analysis = detector.analyze_pdf(working)
                            if analysis:
                                analyses.append(analysis)
                    except Exception as e:
                        logging.warning(f"Per-file analysis failed for {working}: {e}")
        except Exception as e:
            logging.error(f"Detector analysis error: {e}")
            analyses = []

        # Convert analysis objects to serializable dicts similar to analyze_intake_api
        analyses_data = []
        single_count = 0
        batch_count = 0
        # load persisted rotations
        persisted = {}
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS intake_rotations (filename TEXT PRIMARY KEY, rotation INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            for row in cur.execute("SELECT filename, rotation FROM intake_rotations"):
                persisted[row[0]] = int(row[1])
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

        for analysis in analyses:
            filename_only = os.path.basename(analysis.file_path)
            detected_rot = persisted.get(filename_only, analysis.detected_rotation)
            analysis_data = {
                'filename': filename_only,
                'file_size_mb': analysis.file_size_mb,
                'page_count': analysis.page_count,
                'processing_strategy': analysis.processing_strategy,
                'confidence': analysis.confidence,
                'reasoning': analysis.reasoning,
                'filename_hints': analysis.filename_hints,
                'content_sample': analysis.content_sample,
                'llm_analysis': analysis.llm_analysis,
                'detected_rotation': detected_rot
            }
            analyses_data.append(analysis_data)
            if analysis.processing_strategy == 'single_document':
                single_count += 1
            else:
                batch_count += 1

        # Atomic write: write to temp file then replace
        try:
            tmp_target = f"{cache_file}.tmp"
            import pickle as _pickle
            with open(tmp_target, 'wb') as f:
                _pickle.dump(analyses_data, f)
            os.replace(tmp_target, cache_file)
            logging.info(f"Background analysis cached to {cache_file}")
        except Exception as e:
            logging.warning(f"Failed to atomically write cache in background worker: {e}")

        # Trigger process_batch in FAST_TEST_MODE after cache written
        try:
            if os.getenv('FAST_TEST_MODE', '0').lower() in ('1', 'true', 't'):
                from ..processing import process_batch
                logging.info("FAST_TEST_MODE: background worker triggering process_batch")
                try:
                    process_batch()
                except Exception as e:
                    logging.warning(f"process_batch in background failed: {e}")
        except Exception:
            pass

    except Exception as e:
        logging.error(f"Error in background analysis worker: {e}")
    finally:
        # Remove lock file if present
        try:
            lf = os.path.join(select_tmp_dir(), 'intake_analysis_in_progress.lock')
            if os.path.exists(lf):
                os.remove(lf)
        except Exception:
            pass

@intake_bp.route("/analyze_intake")
def analyze_intake_page():
    """Display the intake analysis page with cached results if available."""
    # If all previous batches exported, encourage fresh batch by clearing cached analyses
    try:
        purge_cache = False
        with database_connection() as conn:
            cur = conn.cursor()
            # Detect if there are any non-exported batches; tolerate missing column names
            cur.execute("PRAGMA table_info(batches)")
            cols = [r[1] for r in cur.fetchall()]
            status_col = 'status' if 'status' in cols else None
            if status_col:
                try:
                    row = cur.execute("SELECT COUNT(*) FROM batches WHERE status != 'exported' AND status != 'Exported'").fetchone()
                    if row and row[0] == 0:
                        purge_cache = True
                except Exception:
                    pass
        if purge_cache:
            # If a cached analysis file already exists, it's likely a freshly
            # completed analysis run. Don't purge immediately — doing so causes
            # a race where the client reloads after analysis but the server
            # removes the cache again because batches appear exported in the DB
            # during tests. Only purge when no cache is present.
            import tempfile
            import os as _os
            cache_file = _os.path.join(select_tmp_dir(), 'intake_analysis_cache.pkl')
            if _os.path.exists(cache_file):
                logging.info("Skipping cache purge because analysis cache exists (avoids race)")
            else:
                try:
                    # No cache file present and DB indicates all batches exported - safe to purge
                    # (this branch effectively is a no-op since cache missing)
                    logging.info("No analysis cache present to purge")
                except Exception:
                    pass
    except Exception as _purge_err:
        logging.debug(f"Cache purge check failed: {_purge_err}")
    # Check if we have cached analysis results to avoid re-analyzing
    cached_analyses = None
    try:
        import tempfile
        import pickle
        cache_file = os.path.join(select_tmp_dir(), 'intake_analysis_cache.pkl')
        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as f:
                cached_analyses = pickle.load(f)
            logging.info("Loaded cached analysis results")
    except Exception as e:
        logging.warning(f"Failed to load cached analysis results: {e}")
        cached_analyses = None

    # IMPORTANT: Overlay persisted rotations from DB on top of cached analyses
    # This ensures manual rotations survive page refreshes even if the cache is stale
    try:
        if cached_analyses:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS intake_rotations (filename TEXT PRIMARY KEY, rotation INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            persisted = {row[0]: int(row[1]) for row in cur.execute("SELECT filename, rotation FROM intake_rotations")}
            # Update the detected_rotation for each cached analysis if we have a persisted value
            updated = 0
            for item in cached_analyses:
                fn = item.get('filename') or item.get('file_path')
                if not fn:
                    continue
                # Normalize to basename
                base = os.path.basename(fn)
                if base in persisted:
                    item['detected_rotation'] = persisted[base]
                    updated += 1
            try:
                conn.close()
            except Exception:
                pass
            if updated:
                logging.info(f"Applied {updated} persisted rotation(s) to cached analyses for refresh consistency")
    except Exception as e:
        logging.warning(f"Failed to overlay persisted rotations onto cached analyses: {e}")

    # If caller provided a batch_id (from Batch Control), pass it through so the
    # client can be redirected to the appropriate preview when analysis completes.
    batch_id = request.args.get('batch_id')
    return render_template("intake_analysis.html",
                         analyses=cached_analyses,  # Use cached if available
                         intake_dir=app_config.INTAKE_DIR,
                         batch_id=batch_id)

@intake_bp.route('/api/ensure_batch', methods=['POST'])
def ensure_active_batch():
    """Ensure there is an active batch (create one if none exist or all exported).

    Returns JSON with batch_id.
    """
    try:
        # Use batch_guard to reliably reuse or create an intake batch
        try:
            batch_id = get_or_create_intake_batch()
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        return jsonify({'success': True, 'batch_id': batch_id})
    except Exception as e:
        logging.error(f"ensure_active_batch failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@intake_bp.route("/api/analyze_intake_progress")
def analyze_intake_progress():
    """
    Server-Sent Events endpoint for real-time intake analysis progress.

    This endpoint provides live updates during the document detection and analysis process.
    """
    # Capture remote address once (avoid accessing `request` inside generator)
    try:
        _remote_addr = request.remote_addr
    except Exception:
        _remote_addr = None

    

    def generate_progress():
        """SSE generator that spawns background analysis and polls for cached results."""
        logging.info(f"SSE connection opened for analyze_intake_progress from {_remote_addr}")

        intake_dir = app_config.INTAKE_DIR
        if not os.path.exists(intake_dir):
            payload = {'error': f'Intake directory does not exist: {intake_dir}'}
            yield f"data: {json.dumps(payload)}\n\n"
            return

        tmp_dir = select_tmp_dir()
        os.makedirs(tmp_dir, exist_ok=True)
        cache_file = os.path.join(tmp_dir, 'intake_analysis_cache.pkl')
        lock_file = os.path.join(tmp_dir, 'intake_analysis_in_progress.lock')

        # If no analysis in progress and no cache, start background worker
        if not os.path.exists(cache_file) and not os.path.exists(lock_file):
            try:
                # create lock file to indicate work started
                with open(lock_file, 'w') as lf:
                    lf.write(str(time.time()))
            except Exception:
                pass
            try:
                t = threading.Thread(target=background_analysis_worker, args=(intake_dir, cache_file), daemon=True)
                t.start()
                logging.info("Spawned background analysis thread")
            except Exception as e:
                logging.warning(f"Failed to spawn background analysis thread: {e}")

        # Emit queued message then poll for cache; send keep-alive comments while waiting
        try:
            # Include initial PDF progress counters so tests observing SSE
            # immediately can assert on these keys without waiting for full analysis.
            try:
                files = os.listdir(intake_dir)
                pdf_total = sum(1 for f in files if f.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')))
            except Exception:
                pdf_total = 0
            payload = {'queued': True, 'message': 'Analysis started in background', 'pdf_progress': 0, 'pdf_total': pdf_total}
            yield f"data: {json.dumps(payload)}\n\n"
            # Poll for cache or final result
            waited = 0
            while True:
                if os.path.exists(cache_file):
                    try:
                        import pickle
                        with open(cache_file, 'rb') as f:
                            analyses = pickle.load(f)
                        complete_payload = {
                            'complete': True,
                            'analyses': analyses,
                            'total': len(analyses),
                            'single_count': sum(1 for a in analyses if a.get('processing_strategy') == 'single_document'),
                            'batch_count': sum(1 for a in analyses if a.get('processing_strategy') != 'single_document'),
                            'success': True
                        }
                        yield f"data: {json.dumps(complete_payload)}\n\n"
                    except Exception as e:
                        yield f"data: {json.dumps({'error': str(e), 'success': False})}\n\n"
                    break

                # Keep-alive comment to avoid client timeouts
                yield f": keep-alive\n\n"
                time.sleep(1)
                waited += 1
                # Safety timeout: after ~5 minutes stop polling
                if waited > 300:
                    yield f"data: {json.dumps({'error': 'Timeout waiting for analysis to complete', 'success': False})}\n\n"
                    break
        finally:
            try:
                logging.info(f"SSE connection closed for analyze_intake_progress from {_remote_addr}")
            except Exception:
                pass

    # Wrap the generator to trace each emitted SSE payload and lifecycle
    def _traced_stream(gen, label='intake'):
        try:
            for item in gen:
                try:
                    # Log a short summary of emission (trim large payloads)
                    snippet = item if isinstance(item, str) and len(item) < 200 else (item[:200] + '...')
                    logging.info(f"SSE[{label}] emit ts={time.time()} payload={snippet}")
                except Exception:
                    logging.exception("Failed to log SSE emit")
                yield item
        finally:
            try:
                logging.info(f"SSE[{label}] closed ts={time.time()}")
            except Exception:
                pass

    return Response(_traced_stream(generate_progress(), 'analyze_intake'), mimetype='text/event-stream')

@intake_bp.route("/api/analyze_intake")
def analyze_intake_api():
    """
    API endpoint for intake analysis (fallback for browsers with SSE issues).

    Returns JSON response with analysis results for all files in intake directory.
    """
    try:
        from ..document_detector import get_detector
        # Test-debug: surface intake dir contents when API analyze is invoked
        try:
            intake_files = os.listdir(app_config.INTAKE_DIR) if os.path.exists(app_config.INTAKE_DIR) else []
            logging.info(f"analyze_intake_api called; intake_dir={app_config.INTAKE_DIR} files={intake_files}")
        except Exception as _e:
            logging.info(f"analyze_intake_api could not list intake dir: {_e}")

        # Use the test-friendly select_tmp_dir() so tests and SSE use same cache
        cache_file = os.path.join(select_tmp_dir(), 'intake_analysis_cache.pkl')
        lock_file = os.path.join(select_tmp_dir(), 'intake_analysis_in_progress.lock')

        # If cache is already present, return it synchronously
        if os.path.exists(cache_file):
            try:
                import pickle
                with open(cache_file, 'rb') as f:
                    analyses = pickle.load(f)
                result = {
                    'analyses': analyses,
                    'total': len(analyses),
                    'single_count': sum(1 for a in analyses if a.get('processing_strategy') == 'single_document'),
                    'batch_count': sum(1 for a in analyses if a.get('processing_strategy') != 'single_document'),
                    'success': True,
                    'redirect': None
                }
                try:
                    api_bid = request.args.get('batch_id')
                    if api_bid:
                        result['redirect'] = url_for('manipulation.view_documents', batch_id=int(api_bid))
                except Exception:
                    pass
                return jsonify(result)
            except Exception as e:
                logging.warning(f"Failed to read existing analysis cache: {e}")

        # If an analysis is in progress, respond with 202 Accepted
        if os.path.exists(lock_file):
            return jsonify({'accepted': True, 'message': 'Analysis already in progress'}), 202

        # Start analysis in background and return 202
        try:
            try:
                with open(lock_file, 'w') as lf:
                    lf.write(str(time.time()))
            except Exception:
                pass
            t = threading.Thread(target=background_analysis_worker, args=(app_config.INTAKE_DIR, cache_file), daemon=True)
            t.start()
            logging.info("Started background analysis from analyze_intake_api")
            return jsonify({'accepted': True, 'message': 'Analysis started in background'}), 202
        except Exception as e:
            logging.error(f"Failed to start background analysis: {e}")
            return jsonify({'error': str(e), 'success': False}), 500

    except Exception as e:
        logging.error(f"Error in analyze_intake_api: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


@intake_bp.route('/api/intake_viewer_ready')
def intake_viewer_ready():
    """
    Test/utility endpoint: returns whether the intake analysis viewer will render
    analyses on a GET request. This is intended for tests to poll a deterministic
    server-side signal instead of peeking at temp files from the client.
    """
    try:
        import tempfile
        import os
        import pickle
        cache_file = os.path.join(select_tmp_dir(), 'intake_analysis_cache.pkl')
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    analyses = pickle.load(f)
                count = len(analyses) if analyses else 0
                return jsonify({'ready': True, 'count': count})
            except Exception as e:
                logging.warning(f'Could not read intake cache for readiness probe: {e}')
                return jsonify({'ready': False, 'count': 0, 'error': str(e)}), 200
        return jsonify({'ready': False, 'count': 0}), 200
    except Exception as e:
        logging.error(f'Error in intake_viewer_ready: {e}')
        return jsonify({'ready': False, 'count': 0, 'error': str(e)}), 500

@intake_bp.route("/rescan_ocr", methods=["POST"])
def rescan_ocr():
    """
    API endpoint to rescan OCR for a specific document with manual rotation.

    Expected JSON payload:
    {
        "filename": "document.pdf",
        "rotation": 90
    }
    """
    try:
        data = request.get_json()
        filename = data.get('filename')
        rotation = data.get('rotation', 0)
        quality = (data.get('quality') or 'default').lower()

        if not filename:
            return jsonify({'error': 'Filename is required', 'success': False}), 400

        logging.info(f"[RESCAN_OCR] request filename={filename} rotation={rotation} quality={quality}")

        # Resolve the standardized/converted PDF path for OCR
        file_path = os.path.join(app_config.INTAKE_DIR, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': f'File not found: {filename}', 'success': False}), 404

        # Best-effort: persist rotation on server as well (helps if client save failed)
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS intake_rotations (filename TEXT PRIMARY KEY, rotation INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            cur.execute("UPDATE intake_rotations SET rotation = ?, updated_at = CURRENT_TIMESTAMP WHERE filename = ?", (int(rotation) if isinstance(rotation, int) else 0, filename))
            if cur.rowcount == 0:
                cur.execute("INSERT INTO intake_rotations (filename, rotation) VALUES (?, ?)", (filename, int(rotation) if isinstance(rotation, int) else 0))
            conn.commit()
            conn.close()
            logging.info(f"[RESCAN_OCR] persisted rotation {rotation}° for {filename}")
        except Exception as rot_err:
            logging.warning(f"[RESCAN_OCR] failed to persist rotation for {filename}: {rot_err}")
            try:
                conn.close()
            except Exception:
                pass

        working_pdf = _resolve_working_pdf_path(filename)
        content_sample = _rescan_pdf_ocr(working_pdf, rotation, quality=quality)
        logging.info(f"[RESCAN_OCR] completed for {filename} (chars={len(content_sample) if content_sample else 0})")

        return jsonify({
            'success': True,
            'filename': filename,
            'rotation': rotation,
            'content_sample': content_sample[:500] if content_sample else None,
            'message': f'OCR rescanned successfully with {rotation}° rotation'
        })

    except Exception as e:
        logging.error(f"Error in rescan_ocr: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@intake_bp.route("/reanalyze_llm", methods=["POST"])
def reanalyze_llm():
    """
    API endpoint to re-analyze a document with LLM using updated OCR text.

    Expected JSON payload:
    {
        "filename": "document.pdf"
    }
    """
    try:
        data = request.get_json()
        filename = data.get('filename')

        if not filename:
            return jsonify({'error': 'Filename is required', 'success': False}), 400

        logging.info(f"Re-analyzing LLM for {filename}")

        # Resolve the standardized/converted PDF path for LLM analysis
        file_path = os.path.join(app_config.INTAKE_DIR, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': f'File not found: {filename}', 'success': False}), 404

        # Get current analysis from cache or re-analyze
        from ..document_detector import get_detector
        detector = get_detector(use_llm_for_ambiguous=True)

        working_pdf = _resolve_working_pdf_path(filename)
        analysis = detector.analyze_pdf(working_pdf)

        if not analysis:
            return jsonify({'error': 'Failed to re-analyze document', 'success': False}), 500

        return jsonify({
            'success': True,
            'filename': filename,
            'processing_strategy': analysis.processing_strategy,
            'confidence': analysis.confidence,
            'reasoning': analysis.reasoning,
            'llm_analysis': analysis.llm_analysis,
            'message': 'LLM re-analysis completed successfully'
        })

    except Exception as e:
        logging.error(f"Error in reanalyze_llm: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

def _rescan_pdf_ocr(file_path: str, rotation: int, quality: str = 'default') -> str:
    """
    Re-run OCR on a PDF file with specified rotation.

    Args:
        file_path (str): Path to the PDF file
        rotation (int): Rotation angle (0, 90, 180, 270)

    Returns:
        str: Extracted text content
    """
    try:
        try:
            from pdf2image import convert_from_path
            import pytesseract
        except ImportError as import_error:
            logging.error(f"Missing required dependencies for PDF OCR: {import_error}")
            return "Error: Missing required dependencies for PDF OCR"

        # Convert first few pages to images (higher DPI for high-accuracy mode)
        dpi = 200
        if quality in {"high", "hq", "best"}:
            dpi = 400
        pages = convert_from_path(file_path, first_page=1, last_page=3, dpi=dpi)
        page_texts = []

        for page_idx, page_img in enumerate(pages):
            # Apply rotation if specified
            if rotation != 0:
                page_img = page_img.rotate(-rotation, expand=True)
                logging.info(f"Applied {rotation}° rotation to page {page_idx + 1}")

            # Run Tesseract OCR with tuned config for better accuracy
            tesseract_config = "--oem 1 --psm 6"  # LSTM-only, assume a block of text
            try:
                page_text = pytesseract.image_to_string(page_img, config=tesseract_config)
            except Exception as te:
                logging.warning(f"Tesseract OCR error on page {page_idx + 1}: {te}")
                page_text = ""
            if page_text and len(page_text.strip()) > 10:
                page_texts.append(f"=== PAGE {page_idx + 1} ===\n{page_text.strip()}")
                logging.info(f"Extracted {len(page_text)} characters from rotated page {page_idx + 1}")
            elif quality in {"high", "hq", "best"}:
                # Fallback: try EasyOCR on the rendered image (for low-print quality docs)
                try:
                    import numpy as np
                    try:
                        from ..processing import EasyOCRSingleton
                        reader = EasyOCRSingleton.get_reader()
                    except ImportError:
                        from processing import EasyOCRSingleton
                        reader = EasyOCRSingleton.get_reader()
                    ocr_results = reader.readtext(np.array(page_img))
                    if ocr_results:
                        eo_text = " ".join([t for (_, t, _) in ocr_results]).strip()
                        if eo_text and len(eo_text) > 10:
                            page_texts.append(f"=== PAGE {page_idx + 1} (easyocr) ===\n{eo_text}")
                            logging.info(f"EasyOCR extracted {len(eo_text)} chars from page {page_idx + 1}")
                        else:
                            logging.info(f"EasyOCR found no usable text on page {page_idx + 1}")
                except Exception as eo_err:
                    logging.warning(f"EasyOCR fallback failed on page {page_idx + 1}: {eo_err}")

        combined_text = "\n\n".join(page_texts)
        logging.info(f"Total OCR text extracted: {len(combined_text)} characters")

        return combined_text

    except Exception as e:
        logging.error(f"Error in PDF OCR rescan: {e}")
        return ""

def _rescan_image_ocr(file_path: str, rotation: int) -> str:
    """
    Re-run OCR on an image file with specified rotation.

    Args:
        file_path (str): Path to the image file
        rotation (int): Rotation angle (0, 90, 180, 270)

    Returns:
        str: Extracted text content
    """
    try:
        from PIL import Image
        import numpy as np

        with Image.open(file_path) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Apply rotation if specified
            if rotation != 0:
                img = img.rotate(-rotation, expand=True)
                logging.info(f"Applied {rotation}° rotation to image")

            # Use EasyOCR for better results
            try:
                from ..processing import EasyOCRSingleton
                reader = EasyOCRSingleton.get_reader()
            except ImportError:
                from processing import EasyOCRSingleton
                reader = EasyOCRSingleton.get_reader()
            ocr_results = reader.readtext(np.array(img))

            if ocr_results:
                text = " ".join([text for (_, text, _) in ocr_results])
                logging.info(f"Extracted {len(text)} characters from rotated image")
                return text
            else:
                logging.warning("No text extracted from rotated image")
                return ""

    except Exception as e:
        logging.error(f"Error in image OCR rescan: {e}")
        return ""


@intake_bp.route('/save_rotation', methods=['POST'])
def save_rotation():
    """Save document rotation state for persistence across sessions"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        filename = data.get('filename')
        rotation = data.get('rotation', 0)

        if not filename:
            return jsonify({'error': 'Filename required'}), 400

        logging.info(f"[SAVE_ROTATION] request filename={filename} rotation={rotation}")
        # Upsert rotation in dedicated intake_rotations table
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS intake_rotations (filename TEXT PRIMARY KEY, rotation INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        # Try update first
        cursor.execute("UPDATE intake_rotations SET rotation = ?, updated_at = CURRENT_TIMESTAMP WHERE filename = ?", (rotation, filename))
        if cursor.rowcount == 0:
            cursor.execute("INSERT INTO intake_rotations (filename, rotation) VALUES (?, ?)", (filename, rotation))
        conn.commit()
        conn.close()

        logging.info(f"Saved rotation {rotation}° for {filename}")
        return jsonify({'success': True})

    except Exception as e:
        logging.error(f"Error saving rotation: {e}")
        return jsonify({'error': 'Failed to save rotation'}), 500
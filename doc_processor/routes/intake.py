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
import logging
import json
import os
from pathlib import Path

# Create blueprint for intake routes
intake_bp = Blueprint('intake', __name__)


def _select_tmp_dir() -> str:
    """Select a temporary directory: TEST_TMPDIR -> TMPDIR -> system tempdir -> cwd."""
    try:
        import tempfile
        return os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()
    except Exception:
        return os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or os.getcwd()


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
    tmp_dir = _select_tmp_dir()
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
            cache_file = _os.path.join(_select_tmp_dir(), 'intake_analysis_cache.pkl')
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
        cache_file = os.path.join(_select_tmp_dir(), 'intake_analysis_cache.pkl')
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
    def generate_progress():
        try:
            # Import here to avoid circular imports
            import os

            intake_dir = app_config.INTAKE_DIR
            if not os.path.exists(intake_dir):
                yield f"data: {json.dumps({'error': f'Intake directory does not exist: {intake_dir}'})}\n\n"
                return

            # Clean up any old converted PDFs to ensure fresh start
            import tempfile
            import glob
            temp_dir = _select_tmp_dir()
            old_converted_pdfs = glob.glob(os.path.join(temp_dir, "*_converted.pdf"))
            for old_pdf in old_converted_pdfs:
                try:
                    os.remove(old_pdf)
                    logging.info(f"Cleaned up old converted PDF: {os.path.basename(old_pdf)}")
                except Exception as e:
                    logging.warning(f"Failed to clean up {old_pdf}: {e}")

            # Ensure mapping table exists; we'll repopulate mappings during this run
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS intake_working_files (filename TEXT PRIMARY KEY, working_pdf TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
                conn.commit()
                conn.close()
            except Exception as db_err:
                logging.warning(f"Could not ensure intake_working_files table: {db_err}")
                try:
                    conn.close()
                except Exception:
                    pass

            # Scan intake directory for files - treat ALL as needing conversion
            original_pdf_files = []
            image_files = []

            for f in os.listdir(intake_dir):
                file_ext = os.path.splitext(f)[1].lower()
                file_path = os.path.join(intake_dir, f)
                if file_ext == '.pdf':
                    original_pdf_files.append(file_path)
                elif file_ext in ['.png', '.jpg', '.jpeg']:
                    image_files.append(file_path)

            total_files = len(original_pdf_files) + len(image_files)
            # Total operations = convert all files (PDFs + images) + analyze all converted PDFs
            total_operations = total_files + total_files  # Convert everything + analyze everything

            if total_files == 0:
                yield f"data: {json.dumps({'complete': True, 'analyses': [], 'total': 0, 'single_count': 0, 'batch_count': 0, 'success': True})}\n\n"
                return

            # Send initial progress
            logging.info(f"Starting two-phase analysis for {total_files} files ({len(original_pdf_files)} PDFs, {len(image_files)} images)")
            yield f"data: {json.dumps({'progress': 0, 'total': total_operations, 'current_file': None, 'message': f'Found {total_files} files - starting two-phase processing...'})}\n\n"

            # Phase 1: Convert ALL files to standardized PDFs
            all_converted_pdfs = []
            detector = get_detector(use_llm_for_ambiguous=True)
            current_operation = 0

            yield f"data: {json.dumps({'progress': current_operation, 'total': total_operations, 'current_file': None, 'message': f'Phase 1: Converting {total_files} files to standardized PDFs...'})}\n\n"

            # Convert images to PDFs
            for i, image_path in enumerate(image_files):
                image_name = os.path.basename(image_path)
                current_operation += 1
                yield f"data: {json.dumps({'progress': current_operation, 'total': total_operations, 'current_file': image_name, 'message': f'Converting image {i+1}/{len(image_files)}: {image_name}...'})}\n\n"

                converted_pdf = detector._convert_image_to_pdf(image_path)
                all_converted_pdfs.append(converted_pdf)
                logging.info(f"Converted image: {image_name} -> {os.path.basename(converted_pdf)}")

                # Persist mapping image -> converted PDF
                try:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute("CREATE TABLE IF NOT EXISTS intake_working_files (filename TEXT PRIMARY KEY, working_pdf TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
                    cur.execute("UPDATE intake_working_files SET working_pdf = ?, updated_at = CURRENT_TIMESTAMP WHERE filename = ?", (converted_pdf, image_name))
                    if cur.rowcount == 0:
                        cur.execute("INSERT INTO intake_working_files (filename, working_pdf) VALUES (?, ?)", (image_name, converted_pdf))
                    conn.commit()
                    conn.close()
                except Exception as db_err:
                    logging.warning(f"Failed to persist mapping for {image_name}: {db_err}")
                    try:
                        conn.close()
                    except Exception:
                        pass

            # Copy original PDFs to temp directory for consistent handling
            for i, pdf_path in enumerate(original_pdf_files):
                pdf_name = os.path.basename(pdf_path)
                current_operation += 1
                yield f"data: {json.dumps({'progress': current_operation, 'total': total_operations, 'current_file': pdf_name, 'message': f'Standardizing PDF {i+1}/{len(original_pdf_files)}: {pdf_name}...'})}\n\n"

                # Copy to temp with consistent naming
                temp_pdf_path = os.path.join(temp_dir, f"{Path(pdf_path).stem}_standardized.pdf")
                import shutil
                shutil.copy2(pdf_path, temp_pdf_path)
                all_converted_pdfs.append(temp_pdf_path)
                logging.info(f"Standardized PDF: {pdf_name} -> {os.path.basename(temp_pdf_path)}")

                # Persist mapping original PDF -> standardized copy
                try:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute("CREATE TABLE IF NOT EXISTS intake_working_files (filename TEXT PRIMARY KEY, working_pdf TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
                    cur.execute("UPDATE intake_working_files SET working_pdf = ?, updated_at = CURRENT_TIMESTAMP WHERE filename = ?", (temp_pdf_path, pdf_name))
                    if cur.rowcount == 0:
                        cur.execute("INSERT INTO intake_working_files (filename, working_pdf) VALUES (?, ?)", (pdf_name, temp_pdf_path))
                    conn.commit()
                    conn.close()
                except Exception as db_err:
                    logging.warning(f"Failed to persist mapping for {pdf_name}: {db_err}")
                    try:
                        conn.close()
                    except Exception:
                        pass

            # Phase 2: Analyze all standardized PDFs
            total_pdfs = len(all_converted_pdfs)
            yield f"data: {json.dumps({'progress': current_operation, 'total': total_operations, 'current_file': None, 'message': f'Phase 2: Analyzing {total_pdfs} standardized PDFs...'})}\n\n"

            analyses = []
            single_count = 0
            batch_count = 0

            for i, pdf_path in enumerate(all_converted_pdfs):
                pdf_name = os.path.basename(pdf_path)
                current_operation += 1

                # Send progress update for current PDF analysis. We emit both the
                # aggregate operation counters (progress/total) and PDF-centric
                # counters (pdf_progress/pdf_total) so the UI can show a
                # user-friendly "X of Y PDFs" message while internal logic can
                # still track convert+analyze operations.
                yield f"data: {json.dumps({
                    'progress': current_operation,
                    'total': total_operations,
                    'pdf_progress': i+1,
                    'pdf_total': total_pdfs,
                    'current_file': pdf_name,
                    'message': f'Analyzing PDF {i+1}/{total_pdfs}: {pdf_name}...'
                })}\n\n"

                # Analyze the standardized PDF
                analysis = detector.analyze_pdf(pdf_path)

                # Determine original filename for display
                original_filename = pdf_name
                if "_converted.pdf" in pdf_name:
                    # Find the original image name
                    original_filename = pdf_name.replace("_converted.pdf", "")
                    # Add back original extension
                    for img_path in image_files:
                        if Path(img_path).stem == original_filename:
                            original_filename = os.path.basename(img_path)
                            break
                elif "_standardized.pdf" in pdf_name:
                    # Find the original PDF name
                    original_filename = pdf_name.replace("_standardized.pdf", ".pdf")

                # Load any persisted rotation for this filename
                persisted_rotation = None
                try:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute("CREATE TABLE IF NOT EXISTS intake_rotations (filename TEXT PRIMARY KEY, rotation INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
                    row = cur.execute("SELECT rotation FROM intake_rotations WHERE filename = ?", (original_filename,)).fetchone()
                    if row:
                        persisted_rotation = int(row[0])
                except Exception as rot_err:
                    logging.warning(f"Could not read persisted rotation for {original_filename}: {rot_err}")
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass

                # Prepare analysis data (prefer persisted rotation when available)
                analysis_data = {
                    'filename': original_filename,  # Use original filename for display
                    'file_size_mb': analysis.file_size_mb,
                    'page_count': analysis.page_count,
                    'processing_strategy': analysis.processing_strategy,
                    'confidence': analysis.confidence,
                    'reasoning': analysis.reasoning,
                    'filename_hints': analysis.filename_hints,
                    'content_sample': analysis.content_sample,
                    'llm_analysis': analysis.llm_analysis,  # Include LLM analysis data
                    'detected_rotation': persisted_rotation if persisted_rotation is not None else analysis.detected_rotation,
                    'pdf_path': pdf_path  # Store the actual PDF path for serving
                }

                analyses.append(analysis_data)

                if analysis.processing_strategy == "single_document":
                    single_count += 1
                else:
                    batch_count += 1

            # Cache the analysis results for future use
            import tempfile
            import pickle
            cache_file = os.path.join(tempfile.gettempdir(), 'intake_analysis_cache.pkl')
            try:
                with open(cache_file, 'wb') as f:
                    pickle.dump(analyses, f)
                logging.info(f"Cached analysis results to {cache_file}")
            except Exception as cache_err:
                logging.warning(f"Failed to cache analysis results: {cache_err}")

            # Build completion payload. If caller requested a batch_id, include a redirect
            # to the manipulation view for that batch so the client can follow automatically.
            complete_payload = {
                'complete': True,
                'analyses': analyses,
                'total': total_operations,
                'single_count': single_count,
                'batch_count': batch_count,
                'success': True
            }
            # Respect batch_id query param (if provided by client) for post-analysis redirect
            try:
                b_id = request.args.get('batch_id')
                if b_id:
                    complete_payload['redirect'] = url_for('manipulation.view_documents', batch_id=int(b_id))
            except Exception:
                pass
            yield f"data: {json.dumps(complete_payload)}\n\n"

        except Exception as e:
            logging.error(f"Error in intake analysis SSE: {e}")
            yield f"data: {json.dumps({'error': str(e), 'complete': True, 'success': False})}\n\n"

    return Response(generate_progress(), mimetype='text/event-stream')

@intake_bp.route("/api/analyze_intake")
def analyze_intake_api():
    """
    API endpoint for intake analysis (fallback for browsers with SSE issues).

    Returns JSON response with analysis results for all files in intake directory.
    """
    try:
        from ..document_detector import get_detector

        detector = get_detector(use_llm_for_ambiguous=True)
        analyses = detector.analyze_intake_directory(app_config.INTAKE_DIR)

        # Convert analyses to JSON-serializable format
        analyses_data = []
        single_count = 0
        batch_count = 0

        # Load persisted rotations once
        persisted = {}
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS intake_rotations (filename TEXT PRIMARY KEY, rotation INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            for row in cur.execute("SELECT filename, rotation FROM intake_rotations"):
                persisted[row[0]] = int(row[1])
        except Exception as rot_err:
            logging.warning(f"Could not load persisted intake rotations: {rot_err}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

        for analysis in analyses:
            filename_only = os.path.basename(analysis.file_path)
            detected_rot = persisted.get(filename_only, analysis.detected_rotation)
            analysis_data = {
                'filename': os.path.basename(analysis.file_path),
                'file_size_mb': analysis.file_size_mb,
                'page_count': analysis.page_count,
                'processing_strategy': analysis.processing_strategy,
                'confidence': analysis.confidence,
                'reasoning': analysis.reasoning,
                'filename_hints': analysis.filename_hints,
                'content_sample': analysis.content_sample,
                'llm_analysis': analysis.llm_analysis,  # Include LLM analysis data
                'detected_rotation': detected_rot  # Include rotation info (persisted if available)
            }
            analyses_data.append(analysis_data)

            if analysis.processing_strategy == "single_document":
                single_count += 1
            else:
                batch_count += 1

        # Cache the analysis results for future use
        import tempfile
        import pickle
        cache_file = os.path.join(tempfile.gettempdir(), 'intake_analysis_cache.pkl')
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(analyses_data, f)
            logging.info(f"Cached analysis results to {cache_file}")
        except Exception as cache_err:
            logging.warning(f"Failed to cache analysis results: {cache_err}")

        result = {
            'analyses': analyses_data,
            'total': len(analyses_data),
            'single_count': single_count,
            'batch_count': batch_count,
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
        cache_file = os.path.join(_select_tmp_dir(), 'intake_analysis_cache.pkl')
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
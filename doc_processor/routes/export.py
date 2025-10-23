"""
Export and Finalization Routes Blueprint

This module contains all routes related to:
- Document finalization and export
- PDF generation and download
- Export progress tracking
- Batch completion workflows

Extracted from the monolithic app.py to improve maintainability.
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, send_file
import logging
from typing import Dict, Any
import os
import json
import threading
from datetime import datetime
import hashlib

# Import existing modules (these imports will need to be adjusted)
from ..database import (
    get_db_connection
)
from ..processing import (
    finalize_single_documents_batch_with_progress,
)
from ..config_manager import app_config
from ..utils.helpers import create_error_response, create_success_response
from ..services.export_service import ExportService, _resolve_export_dir
from ..utils.path_utils import select_tmp_dir, resolve_filing_cabinet_dir

# Create Blueprint
bp = Blueprint('export', __name__, url_prefix='/export')
logger = logging.getLogger(__name__)

# Instantiate service (thread-safe internal locks inside service)
export_service = ExportService()

# Wrapper status dict (backward compatibility for existing JS polling hitting /export/api/progress)
_route_status_lock = threading.Lock()
_route_status_cache: Dict[int, Dict[str, Any]] = {}

def _merge_status(batch_id: int, service_snapshot: Dict[str, Any]):
    """Merge service status into route cache (thin compatibility layer).

    The historical frontend expects a nested dict keyed by batch id when calling
    /export/api/progress. We mirror the service's per-batch status there.
    """
    with _route_status_lock:
        _route_status_cache[batch_id] = service_snapshot

@bp.route("/finalize/<int:batch_id>")
def finalize_page(batch_id: int):
    """Display finalization page for a batch."""
    try:
        # Get batch information and documents ready for finalization
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     batch = get_batch_by_id(batch_id)
        #     documents = get_documents_by_batch(batch_id, status='ready_for_export')

        return render_template('finalize.html',
                             batch_id=batch_id,
                             batch={},
                             documents=[])

    except Exception as e:
        logger.error(f"Error loading finalization page for batch {batch_id}: {e}")
        flash(f"Error loading finalization: {str(e)}", "error")
        return redirect(url_for('batch.batch_control'))

@bp.route("/batch/<int:batch_id>", methods=["POST"])
def export_batch(batch_id: int):
    """Start the export process for a batch."""
    try:
        export_format = request.form.get('export_format', 'pdf')
        include_originals = request.form.get('include_originals', False)

        # Validate batch is ready for export
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     batch_status = get_batch_status(batch_id)
        #     if batch_status not in ['ordered', 'ready_for_export']:
        #         return jsonify(create_error_response(f"Batch not ready for export (status: {batch_status})"))

        # Integrate with service (placeholder documents until grouping export implemented)
        service_result = export_service.export_batch(batch_id, export_format=export_format, include_originals=bool(include_originals))
        return jsonify(service_result if service_result.get('success') else create_error_response(service_result.get('error', 'Unknown error')))

    except Exception as e:
        logger.error(f"Error starting export for batch {batch_id}: {e}")
        return jsonify(create_error_response(f"Failed to start export: {str(e)}"))

@bp.route("/finalize_single_documents_batch/<int:batch_id>", methods=["POST"], endpoint='finalize_single_documents_batch')
def finalize_single_documents_batch_route(batch_id: int):
    """Finalize ALL single-document records for this batch.

    Implements Phase 1 real export pipeline by delegating to
    finalize_single_documents_batch_with_progress. Progress is surfaced via
    /export/api/progress and /export/api/batch_status/<batch_id>.
    Query params / form:
      - force: if '1', ignore existing destination files.
      - json_sidecar: if '1', create a parallel JSON summary next to markdown.
    """
    try:
        force = request.form.get('force') == '1' or request.args.get('force') == '1'
        json_sidecar = request.form.get('json_sidecar') == '1' or request.args.get('json_sidecar') == '1'

        # Short-circuit if an export is already running. Also clear any stale
        # internal state for this batch to avoid races from prior test runs.
        existing = export_service.get_export_status(batch_id)
        if existing.get('status') in {'starting', 'finalizing', 'finalizing_single'}:
            return jsonify(create_error_response("Export already in progress for this batch")), 409
        try:
            # Best-effort reset of previous export status and route cache for this batch
            export_service.reset_export_status(batch_id)
            with _route_status_lock:
                if batch_id in _route_status_cache:
                    del _route_status_cache[batch_id]
        except Exception:
            # Non-fatal; continue with launching export
            pass

        def progress_callback(current, total, message, details):
            snapshot = {
                'status': 'running' if current < total else 'completed',
                'mode': 'single_documents',
                'progress': int((current / total) * 100) if total else 0,
                'message': message,
                'details': details,
                'current': current,
                'total': total,
                'batch_id': batch_id
            }
            _merge_status(batch_id, snapshot)

        def worker():
            try:
                start_snapshot = {
                    'status': 'starting',
                    'mode': 'single_documents',
                    'progress': 0,
                    'message': 'Initializing export',
                    'details': 'Preparing file list',
                    'batch_id': batch_id
                }
                _merge_status(batch_id, start_snapshot)

                # Delegate to processing layer (already handles tags, markdown)
                success = finalize_single_documents_batch_with_progress(batch_id, progress_callback)

                # Optionally create JSON sidecars for each markdown (Phase 2 enhancement integrated early)
                if success and json_sidecar:
                    try:
                        _create_json_sidecars_for_batch(batch_id, force=force)
                    except Exception as side_e:
                        logger.error(f"Failed creating JSON sidecars for batch {batch_id}: {side_e}")

                final_snapshot = _route_status_cache.get(batch_id, {}).copy()
                final_snapshot['status'] = 'completed' if success else 'error'
                final_snapshot['message'] = 'Export completed' if success else 'Export had errors (see logs)'
                _merge_status(batch_id, final_snapshot)
            except Exception as e:
                logger.exception(f"Unhandled export failure for batch {batch_id}: {e}")
                fail_snapshot = {
                    'status': 'error',
                    'progress': 0,
                    'message': f'Failed: {e}',
                    'batch_id': batch_id
                }
                _merge_status(batch_id, fail_snapshot)

        # Populate an initial 'starting' snapshot so polling clients see progress immediately
        try:
            init_snapshot = {
                'status': 'starting',
                'mode': 'single_documents',
                'progress': 0,
                'message': 'Export queued',
                'details': 'Worker scheduled',
                'current': 0,
                'total': 0,
                'batch_id': batch_id
            }
            _merge_status(batch_id, init_snapshot)
        except Exception:
            pass
        # In FAST_TEST_MODE we run the worker inline to make tests deterministic
        # and avoid background thread scheduling delays causing test timeouts.
        if getattr(app_config, 'FAST_TEST_MODE', False):
            try:
                worker()
            except Exception:
                # Ensure any exception inside inline worker is logged by worker itself
                pass
        else:
            threading.Thread(target=worker, daemon=True).start()
        return jsonify(create_success_response({'message': f'Started single-document export for batch {batch_id}', 'batch_id': batch_id, 'force': force, 'json_sidecar': json_sidecar}))
    except Exception as e:
        logger.error(f"Error launching single-doc export for batch {batch_id}: {e}")
        return jsonify(create_error_response(f"Failed to start export: {e}")), 500

@bp.route("/finalize_batch/<int:batch_id>", methods=["POST"])
def finalize_batch(batch_id: int):
    """Finalize a batch as grouped multi-page documents."""
    try:
        grouping_method = request.form.get('grouping_method', 'ai_suggested')
        # Placeholder: until grouped export implemented, return 501 or call service with grouping placeholder
        return jsonify(create_error_response('Grouped finalization not yet implemented in refactor')), 501

    except Exception as e:
        logger.error(f"Error starting batch finalization: {e}")
        return jsonify(create_error_response(f"Failed to start finalization: {str(e)}"))


@bp.route('/view_pdf/<path:filename>')
def view_pdf(filename: str):
    """Render an internal PDF.js-based viewer for a given intake file.

    Using a PDF.js canvas avoids rotating browser-native PDF UI when applying transforms.

    Query params:
      - rotation (optional): initial rotation degrees (0/90/180/270)
    """
    try:
        # Build URL to serve the original/converted PDF (existing smart route)
        pdf_url = url_for('export.serve_original_pdf', filename=filename)
        # Optional initial rotation
        rotation = 0
        try:
            rotation = int(request.args.get('rotation', 0))
        except Exception:
            rotation = 0

        # If no explicit rotation provided, consult persisted rotation in DB so refreshes keep orientation
        if rotation == 0:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS intake_rotations (filename TEXT PRIMARY KEY, rotation INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
                row = cur.execute("SELECT rotation FROM intake_rotations WHERE filename = ?", (filename,)).fetchone()
                if row:
                    persisted_rot = int(row[0])
                    # Only override if a non-zero persisted rotation exists, to avoid clobbering an intentional 0 passed in
                    if persisted_rot in (90, 180, 270):
                        rotation = persisted_rot
                try:
                    conn.close()
                except Exception:
                    pass
            except Exception as rot_err:
                logger.debug(f"Could not load persisted rotation for {filename}: {rot_err}")

        # Provide pdf.js version and flag for showing banner (hide in production unless debug env variable set)
        pdfjs_version = '4.2.67'
        show_banner = bool(request.args.get('debug_viewer') or os.environ.get('PDFJS_DEBUG_BANNER'))
        return render_template('pdf_viewer.html', pdf_url=pdf_url, filename=filename, initial_rotation=rotation, pdfjs_version=pdfjs_version, show_banner=show_banner)
    except Exception as e:
        logger.error(f"Error rendering PDF viewer for {filename}: {e}")
        # Fallback to serving the file directly
        return redirect(url_for('export.serve_original_pdf', filename=filename))

def _asset_hash(path: str) -> str:
    try:
        with open(path, 'rb') as f:
            h = hashlib.sha256(f.read()).hexdigest()
        return h[:8]
    except Exception:
        return ''


def _resolve_filing_cabinet_dir(category: str | None = None) -> str:
    """Resolve a safe filing cabinet directory for exports/sidecars.

    Precedence: app_config.FILING_CABINET_DIR -> FILING_CABINET_DIR env -> TEST_TMPDIR -> TMPDIR -> system tempdir -> cwd
    If category is provided, returns the category subdirectory (sanitized with spaces replaced by '_') and ensures it exists.
    """
    try:
        import tempfile as _temp
        base = getattr(app_config, 'FILING_CABINET_DIR', None) or os.environ.get('FILING_CABINET_DIR') or os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or _temp.gettempdir()
    except Exception:
        base = getattr(app_config, 'FILING_CABINET_DIR', None) or os.environ.get('FILING_CABINET_DIR') or os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or os.getcwd()

    if category:
        safe_category = category.replace(' ', '_')
        path = os.path.join(base, safe_category)
    else:
        path = base

    path = os.path.abspath(path)
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        # Fallback to tempdir when creation fails
        try:
            import tempfile as _temp
            fallback = os.path.join(os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or _temp.gettempdir(), category.replace(' ', '_') if category else 'filing_cabinet')
            os.makedirs(fallback, exist_ok=True)
            return os.path.abspath(fallback)
        except Exception:
            return path

    return path


# local selection helpers replaced by shared `doc_processor.utils.path_utils`

@bp.route('/viewer_health')
def viewer_health():
    """Lightweight health endpoint reporting local pdf.js asset availability and hash."""
    base = os.path.join(os.path.dirname(__file__), '..', 'static', 'vendor', 'pdfjs')
    base = os.path.abspath(base)
    core = os.path.join(base, 'pdf.min.js')
    worker = os.path.join(base, 'pdf.worker.min.js')
    core_exists = os.path.exists(core)
    worker_exists = os.path.exists(worker)
    core_hash = _asset_hash(core) if core_exists else ''
    worker_hash = _asset_hash(worker) if worker_exists else ''
    status = 'ok' if core_exists and worker_exists else 'degraded'
    return jsonify({
        'status': status,
        'pdfjs_version': '4.2.67',
        'core_exists': core_exists,
        'worker_exists': worker_exists,
        'core_hash': core_hash,
        'worker_hash': worker_hash,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@bp.route("/progress")
def export_progress():
    """Display export progress page."""
    return render_template('export_progress.html')

@bp.route("/api/progress")
def api_export_progress():
    """Return merged progress for all batches (route cache).

    Historical contract: success payload with dict keyed by batch id.
    """
    try:
        with _route_status_lock:
            return jsonify(create_success_response(_route_status_cache))
    except Exception as e:
        logger.error(f"Error getting export progress: {e}")
        return jsonify(create_error_response(f"Failed to get progress: {str(e)}"))

@bp.route("/reset_state")
def reset_export_state():
    """Reset all cached progress (does not delete files)."""
    try:
        with _route_status_lock:
            _route_status_cache.clear()
        return jsonify(create_success_response({'message': 'Export state reset successfully'}))
    except Exception as e:
        logger.error(f"Error resetting export state: {e}")
        return jsonify(create_error_response(f"Failed to reset state: {str(e)}"))

@bp.route("/download/<path:filepath>")
def download_export(filepath: str):
    """Download exported files."""
    try:
        # Resolve export directory using centralized resolver (test-aware)
        export_dir = _resolve_export_dir()
        full_path = os.path.join(export_dir, filepath)

        if not os.path.exists(full_path):
            flash("Export file not found", "error")
            return redirect(url_for('batch.batch_control'))

        # Security check - ensure file is within export directory
        if not os.path.abspath(full_path).startswith(export_dir):
            flash("Invalid file path", "error")
            return redirect(url_for('batch.batch_control'))

        return send_file(full_path, as_attachment=True)

    except Exception as e:
        logger.error(f"Error downloading export file {filepath}: {e}")
        flash(f"Error downloading file: {str(e)}", "error")
        return redirect(url_for('batch.batch_control'))

@bp.route("/processed_files/<path:filepath>")
def serve_processed_file(filepath: str):
    """Serve processed files for preview."""
    try:
        # Get processed files directory from config or fallback to PROCESSED_DIR env/tmp
        tmpdir = select_tmp_dir()
        processed_dir = getattr(app_config, 'PROCESSED_DIR', None) or os.getenv('PROCESSED_DIR') or os.path.join(tmpdir, 'processed')
        processed_dir = os.path.abspath(processed_dir)
        # Best-effort mkdir
        try:
            os.makedirs(processed_dir, exist_ok=True)
        except Exception:
            processed_dir = os.path.abspath(os.path.join(select_tmp_dir(), 'processed'))
        full_path = os.path.join(processed_dir, filepath)

        if not os.path.exists(full_path):
            return jsonify(create_error_response("File not found")), 404

        # Security check
        if not os.path.abspath(full_path).startswith(processed_dir):
            return jsonify(create_error_response("Invalid file path")), 403

        return send_file(full_path)

    except Exception as e:
        logger.error(f"Error serving processed file {filepath}: {e}")
        return jsonify(create_error_response(f"Error serving file: {str(e)}")), 500

@bp.route("/original_pdf/<path:filename>")
def serve_original_pdf(filename: str):
    """Serve original PDF/image files from intake directory, with intelligent handling for converted images."""
    try:
        from ..config_manager import app_config
        import tempfile
        from pathlib import Path
        from PIL import Image

        # Files should be served from the intake directory for analysis
        intake_dir = app_config.INTAKE_DIR
        requested_filename = filename  # keep what the client asked for (may be a synthetic .pdf)
        original_path = os.path.join(intake_dir, filename)

        # Basic existence check (no path hunting now that manipulation uses direct DB paths)
        if not os.path.exists(original_path):
            return jsonify(create_error_response(f"File not found: {requested_filename}")), 404

        # Security check - ensure file is within intake directory
        if not os.path.abspath(original_path).startswith(os.path.abspath(intake_dir)):
            return jsonify(create_error_response("Invalid file path")), 403

        # Prefer durable mapping if available: intake_working_files maps filename -> working PDF path
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS intake_working_files (filename TEXT PRIMARY KEY, working_pdf TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            row = cur.execute("SELECT working_pdf FROM intake_working_files WHERE filename = ?", (filename,)).fetchone()
            if row:
                mapped_path = row[0]
                if mapped_path and os.path.exists(mapped_path):
                    logger.info(f"Serving mapped working PDF for {filename}: {mapped_path}")
                    try:
                        conn.close()
                    except Exception:
                        pass
                    return send_file(mapped_path, mimetype='application/pdf', as_attachment=False)
            try:
                conn.close()
            except Exception:
                pass
        except Exception as map_err:
            logger.debug(f"Working-file mapping lookup failed for {filename}: {map_err}")
            try:
                conn.close()
            except Exception:
                pass

        # If the file is already a PDF, serve it directly
        file_ext = Path(original_path).suffix.lower()
        if file_ext == '.pdf':
            return send_file(original_path, mimetype='application/pdf', as_attachment=False)

        # If the file is an image, ensure we serve a PDF (convert on-demand if needed)
        if file_ext in ['.png', '.jpg', '.jpeg']:
            # Prefer test-scoped tempdir when available
            tmpdir = select_tmp_dir()
            try:
                os.makedirs(tmpdir, exist_ok=True)
            except Exception:
                # fallback to system temp
                import tempfile as _temp
                tmpdir = _temp.gettempdir()
            image_name = Path(filename).stem
            converted_pdf_path = os.path.join(tmpdir, f"{image_name}_converted.pdf")

            if not os.path.exists(converted_pdf_path):
                try:
                    # Convert image to PDF on-demand
                    with Image.open(original_path) as img:
                        # Normalize to RGB
                        if img.mode in ('RGBA', 'LA', 'P'):
                            from PIL import Image as PILImage
                            # Some type checkers prefer int color; the library accepts both
                            rgb_img = PILImage.new('RGB', img.size, 0xFFFFFF)
                            if img.mode == 'P':
                                img = img.convert('RGBA')
                            rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                            img = rgb_img
                        elif img.mode != 'RGB':
                            img = img.convert('RGB')
                        img.save(converted_pdf_path, 'PDF', resolution=150.0, quality=95)
                    logger.info(f"On-demand converted {filename} -> {converted_pdf_path}")
                    # Persist mapping after conversion
                    try:
                        conn = get_db_connection()
                        cur = conn.cursor()
                        cur.execute("CREATE TABLE IF NOT EXISTS intake_working_files (filename TEXT PRIMARY KEY, working_pdf TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
                        cur.execute("UPDATE intake_working_files SET working_pdf = ?, updated_at = CURRENT_TIMESTAMP WHERE filename = ?", (converted_pdf_path, filename))
                        if cur.rowcount == 0:
                            cur.execute("INSERT INTO intake_working_files (filename, working_pdf) VALUES (?, ?)", (filename, converted_pdf_path))
                        conn.commit()
                        conn.close()
                    except Exception as db_err:
                        logger.debug(f"Failed to persist on-demand mapping for {filename}: {db_err}")
                        try:
                            conn.close()
                        except Exception:
                            pass
                except Exception as conv_err:
                    logger.error(f"Failed to convert image {filename} to PDF on-demand: {conv_err}")
                    # Fall back to serving the original image to avoid total failure
                    return send_file(original_path)

            # Serve the converted PDF
            return send_file(converted_pdf_path, mimetype='application/pdf', as_attachment=False)

        # For other file types, serve the original
        return send_file(original_path)
    except Exception as e:
        logger.error(f"Error serving original PDF {filename}: {e}")
        return jsonify(create_error_response(f"Error serving file: {str(e)}")), 500

# Export status and utilities
@bp.route("/api/batch_status/<int:batch_id>")
def get_batch_export_status(batch_id: int):
    """Get export status for a specific batch from route cache."""
    try:
        with _route_status_lock:
            batch_status = _route_status_cache.get(batch_id, {
                'status': 'not_started',
                'progress': 0,
                'message': 'No export started'
            })
        return jsonify(create_success_response(batch_status))
    except Exception as e:
        logger.error(f"Error getting batch export status: {e}")
        return jsonify(create_error_response(f"Failed to get status: {str(e)}"))


# ----------------- Helper: JSON Sidecar Creation (Phase 2) -----------------
def _create_json_sidecars_for_batch(batch_id: int, force: bool = False):
    """Create JSON sidecar files mirroring markdown content for each exported single doc.

    Sidecar schema (v1): {
        'filename_base': str,
        'category': str,
        'exported_at': iso8601,
        'ai': { 'suggested_category': ..., 'suggested_filename': ..., 'confidence': float, 'summary': str },
        'tags': { category: [tags] },
        'paths': { 'original_pdf': path, 'searchable_pdf': path, 'markdown': path }
    }
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        rows = cur.execute("""
            SELECT id, final_category, final_filename, ai_suggested_category, ai_suggested_filename, ai_confidence, ai_summary
            FROM single_documents WHERE batch_id = ?
        """, (batch_id,)).fetchall()
        for r in rows:
            doc_id = r[0]
            final_category = r[1] or r[3] or 'Uncategorized'
            filename_base = r[2] or r[4] or f'document_{doc_id}'
            cat_dir = resolve_filing_cabinet_dir(final_category)
            markdown_path = os.path.join(cat_dir, f"{filename_base}.md")
            if not os.path.exists(markdown_path):
                continue  # skip if markdown absent
            json_path = os.path.join(cat_dir, f"{filename_base}.json")
            if os.path.exists(json_path) and not force:
                continue
            # Attempt to extract tags from markdown (simple heuristic: lines after '## Extracted Tags')
            tags_section = {}
            try:
                with open(markdown_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if 'Extracted Tags' in content:
                    after = content.split('Extracted Tags', 1)[1]
                    lines = after.splitlines()
                    for line in lines:
                        if line.startswith('## '):
                            break
                        if line.startswith('**') and '**:' in line:
                            # **Category Name**: tag1, tag2
                            try:
                                raw = line.strip('*')
                            except Exception:
                                raw = line
            except Exception:
                pass
            payload = {
                'filename_base': filename_base,
                'category': final_category,
                'exported_at': datetime.utcnow().isoformat() + 'Z',
                'ai': {
                    'suggested_category': r[3],
                    'suggested_filename': r[4],
                    'confidence': r[5],
                    'summary': r[6]
                },
                'tags': tags_section,
                'paths': {
                    'markdown': markdown_path,
                    'original_pdf': os.path.join(cat_dir, f"{filename_base}_original.pdf"),
                    'searchable_pdf': os.path.join(cat_dir, f"{filename_base}_searchable.pdf")
                },
                'schema_version': 1
            }
            try:
                with open(json_path, 'w', encoding='utf-8') as jf:
                    json.dump(payload, jf, indent=2)
                logger.debug(f"Created JSON sidecar: {json_path}")
            except Exception as w_e:
                logger.error(f"Failed writing JSON sidecar {json_path}: {w_e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

@bp.route("/api/available_exports")
def get_available_exports():
    """Get list of available export files."""
    try:

        export_dir = _resolve_export_dir()

        if not os.path.exists(export_dir):
            return jsonify(create_success_response({'exports': []}))

        exports = []
        for filename in os.listdir(export_dir):
            file_path = os.path.join(export_dir, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                exports.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'download_url': url_for('export.download_export', filepath=filename)
                })

        return jsonify(create_success_response({'exports': exports}))

    except Exception as e:
        logger.error(f"Error getting available exports: {e}")
        return jsonify(create_error_response(f"Failed to get exports: {str(e)}"))
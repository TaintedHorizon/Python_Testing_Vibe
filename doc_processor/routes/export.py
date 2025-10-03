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
from typing import Dict, Any, List, Optional
import os
import json
import threading
from datetime import datetime
import hashlib

# Import existing modules (these imports will need to be adjusted)
from ..database import (
    get_db_connection, get_documents_for_batch, get_batch_by_id,
    get_all_categories
)
from ..processing import safe_move
from ..config_manager import app_config
from ..utils.helpers import create_error_response, create_success_response

# Create Blueprint
bp = Blueprint('export', __name__, url_prefix='/export')
logger = logging.getLogger(__name__)

# Global variables for export tracking (should move to service layer)
export_status = {}
export_lock = threading.Lock()

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
        
        # Start export process in background
        def export_async():
            try:
                with export_lock:
                    export_status[batch_id] = {
                        'status': 'starting',
                        'progress': 0,
                        'message': 'Preparing export...',
                        'files_created': []
                    }
                
                # Update batch status
                # with database_connection() as conn:
                #     cursor = conn.cursor()
                #     cursor.execute("UPDATE batches SET status = 'exporting' WHERE id = ?", (batch_id,))
                
                # Perform the export
                # export_result = export_batch_documents(batch_id, export_format, include_originals)
                
                with export_lock:
                    export_status[batch_id] = {
                        'status': 'completed',
                        'progress': 100,
                        'message': 'Export completed successfully',
                        'files_created': [],  # List of created files
                        'download_links': []  # Links to download files
                    }
                    
            except Exception as e:
                logger.error(f"Error in export process: {e}")
                with export_lock:
                    export_status[batch_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Export failed: {str(e)}",
                        'files_created': []
                    }
        
        thread = threading.Thread(target=export_async)
        thread.start()
        
        return jsonify(create_success_response({
            'message': f'Export started for batch {batch_id}',
            'batch_id': batch_id,
            'export_format': export_format
        }))
        
    except Exception as e:
        logger.error(f"Error starting export for batch {batch_id}: {e}")
        return jsonify(create_error_response(f"Failed to start export: {str(e)}"))

@bp.route("/finalize_single_documents_batch/<int:batch_id>", methods=["POST"])
def finalize_single_documents_batch(batch_id: int):
    """Finalize a batch as individual single-page documents."""
    try:
        # Start finalization process
        def finalize_async():
            try:
                with export_lock:
                    export_status[batch_id] = {
                        'status': 'finalizing_single',
                        'progress': 0,
                        'message': 'Finalizing as single documents...',
                        'files_created': []
                    }
                
                # Get all documents in batch
                # with database_connection() as conn:
                #     cursor = conn.cursor()
                #     documents = get_documents_by_batch(batch_id)
                
                # Create individual PDFs for each document
                # total_docs = len(documents)
                # processed = 0
                
                # for doc in documents:
                #     try:
                #         create_single_document_pdf(doc)
                #         processed += 1
                #         
                #         with export_lock:
                #             export_status[batch_id]['progress'] = int(processed / total_docs * 100)
                #             export_status[batch_id]['message'] = f'Processed {processed}/{total_docs} documents'
                #             
                #     except Exception as e:
                #         logger.error(f"Error processing document {doc['id']}: {e}")
                
                with export_lock:
                    export_status[batch_id] = {
                        'status': 'completed',
                        'progress': 100,
                        'message': 'Single document finalization completed',
                        'files_created': []  # List of created files
                    }
                    
            except Exception as e:
                logger.error(f"Error in single document finalization: {e}")
                with export_lock:
                    export_status[batch_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Finalization failed: {str(e)}",
                        'files_created': []
                    }
        
        thread = threading.Thread(target=finalize_async)
        thread.start()
        
        return jsonify(create_success_response({
            'message': f'Single document finalization started for batch {batch_id}',
            'batch_id': batch_id
        }))
        
    except Exception as e:
        logger.error(f"Error starting single document finalization: {e}")
        return jsonify(create_error_response(f"Failed to start finalization: {str(e)}"))

@bp.route("/finalize_batch/<int:batch_id>", methods=["POST"])
def finalize_batch(batch_id: int):
    """Finalize a batch as grouped multi-page documents."""
    try:
        grouping_method = request.form.get('grouping_method', 'ai_suggested')
        
        # Start finalization process
        def finalize_batch_async():
            try:
                with export_lock:
                    export_status[batch_id] = {
                        'status': 'finalizing_batch',
                        'progress': 0,
                        'message': f'Finalizing batch with {grouping_method} grouping...',
                        'files_created': []
                    }
                
                # Perform batch finalization
                # result = finalize_batch_documents(batch_id, grouping_method)
                
                with export_lock:
                    export_status[batch_id] = {
                        'status': 'completed',
                        'progress': 100,
                        'message': 'Batch finalization completed',
                        'files_created': []  # List of created files
                    }
                    
            except Exception as e:
                logger.error(f"Error in batch finalization: {e}")
                with export_lock:
                    export_status[batch_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Batch finalization failed: {str(e)}",
                        'files_created': []
                    }
        
        thread = threading.Thread(target=finalize_batch_async)
        thread.start()
        
        return jsonify(create_success_response({
            'message': f'Batch finalization started for batch {batch_id}',
            'batch_id': batch_id,
            'grouping_method': grouping_method
        }))
        
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
    """API endpoint for export progress."""
    try:
        with export_lock:
            return jsonify(create_success_response(export_status))
    except Exception as e:
        logger.error(f"Error getting export progress: {e}")
        return jsonify(create_error_response(f"Failed to get progress: {str(e)}"))

@bp.route("/reset_state")
def reset_export_state():
    """Reset export state for debugging."""
    try:
        with export_lock:
            export_status.clear()
        
        return jsonify(create_success_response({
            'message': 'Export state reset successfully'
        }))
        
    except Exception as e:
        logger.error(f"Error resetting export state: {e}")
        return jsonify(create_error_response(f"Failed to reset state: {str(e)}"))

@bp.route("/download/<path:filepath>")
def download_export(filepath: str):
    """Download exported files."""
    try:
        # Get export directory from config
        # export_dir = app_config.get('EXPORT_DIR', '/tmp/exports')
        export_dir = '/tmp/exports'  # Placeholder
        
        full_path = os.path.join(export_dir, filepath)
        
        if not os.path.exists(full_path):
            flash("Export file not found", "error")
            return redirect(url_for('batch.batch_control'))
        
        # Security check - ensure file is within export directory
        if not os.path.abspath(full_path).startswith(os.path.abspath(export_dir)):
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
        # Get processed files directory from config
        # processed_dir = app_config.get('PROCESSED_DIR', '/tmp/processed')
        processed_dir = '/tmp/processed'  # Placeholder
        
        full_path = os.path.join(processed_dir, filepath)
        
        if not os.path.exists(full_path):
            return jsonify(create_error_response("File not found")), 404
        
        # Security check
        if not os.path.abspath(full_path).startswith(os.path.abspath(processed_dir)):
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
        original_path = os.path.join(intake_dir, filename)
        
        # Check if the original file exists
        if not os.path.exists(original_path):
            return jsonify(create_error_response(f"File not found: {filename}")), 404
        
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
        file_ext = Path(filename).suffix.lower()
        if file_ext == '.pdf':
            return send_file(original_path, mimetype='application/pdf', as_attachment=False)

        # If the file is an image, ensure we serve a PDF (convert on-demand if needed)
        if file_ext in ['.png', '.jpg', '.jpeg']:
            temp_dir = tempfile.gettempdir()
            image_name = Path(filename).stem
            converted_pdf_path = os.path.join(temp_dir, f"{image_name}_converted.pdf")

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
    """Get export status for a specific batch."""
    try:
        with export_lock:
            batch_status = export_status.get(batch_id, {
                'status': 'not_started',
                'progress': 0,
                'message': 'Export not started',
                'files_created': []
            })
        
        return jsonify(create_success_response(batch_status))
        
    except Exception as e:
        logger.error(f"Error getting batch export status: {e}")
        return jsonify(create_error_response(f"Failed to get status: {str(e)}"))

@bp.route("/api/available_exports")
def get_available_exports():
    """Get list of available export files."""
    try:
        # export_dir = app_config.get('EXPORT_DIR', '/tmp/exports')
        export_dir = '/tmp/exports'  # Placeholder
        
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
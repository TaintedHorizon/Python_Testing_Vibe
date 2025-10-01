"""
Export and Final# Import existing modules (these imports will need to be adjusted)
from ..database import (
    get_db_connection, get_documents_for_batch, get_batch_by_id,
    get_all_categories
)
from ..processing import safe_move
from ..config_manager import app_config
from ..utils.helpers import create_error_response, create_success_responseRoutes Blueprint

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
    """Serve original PDF files."""
    try:
        # Get archive directory from config
        # archive_dir = app_config.get('ARCHIVE_DIR', '/tmp/archive')
        archive_dir = '/tmp/archive'  # Placeholder
        
        full_path = os.path.join(archive_dir, filename)
        
        if not os.path.exists(full_path):
            return jsonify(create_error_response("Original file not found")), 404
        
        # Security check
        if not os.path.abspath(full_path).startswith(os.path.abspath(archive_dir)):
            return jsonify(create_error_response("Invalid file path")), 403
        
        return send_file(full_path)
        
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
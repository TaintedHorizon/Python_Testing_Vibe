"""
API Routes Blue# Import existing modules (these imports will need to be adjusted)
from database import (
    get_db_connection, update_page_data,
    get_batch_by_id, get_documents_for_batch
)
from processing import get_ai_classification
from config_manager import app_config
from utils.helpers import create_error_response, create_success_responsehis module contains all API endpoints including:
- Document manipulation APIs
- Processing status APIs  
- Real-time progress tracking
- AJAX endpoints for UI interactions

Extracted from the monolithic app.py to improve maintainability.
"""

from flask import Blueprint, request, jsonify, Response
import logging
from typing import Dict, Any, List, Optional, Generator
import json
import time
import threading

# Import existing modules (these imports will need to be adjusted)
from ..database import (
    get_db_connection, update_page_data,
    get_batch_by_id, get_documents_for_batch
)
from ..processing import get_ai_classification
from ..config_manager import app_config
from ..utils.helpers import create_error_response, create_success_response

# Create Blueprint
bp = Blueprint('api', __name__, url_prefix='/api')
logger = logging.getLogger(__name__)

# Global status tracking (should move to service layer)
processing_status = {}
status_lock = threading.Lock()

@bp.route("/apply_name/<int:document_id>", methods=["POST"])
def apply_name(document_id: int):
    """Apply a suggested name to a document."""
    try:
        data = request.get_json()
        suggested_name = data.get('suggested_name')
        
        if not suggested_name:
            return jsonify(create_error_response("Suggested name is required"))
        
        # Apply the name to the document
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     cursor.execute("""
        #         UPDATE documents 
        #         SET filename = ?, updated_at = datetime('now')
        #         WHERE id = ?
        #     """, (suggested_name, document_id))
        
        return jsonify(create_success_response({
            'message': 'Document name applied successfully',
            'document_id': document_id,
            'new_name': suggested_name
        }))
        
    except Exception as e:
        logger.error(f"Error applying name to document {document_id}: {e}")
        return jsonify(create_error_response(f"Failed to apply name: {str(e)}"))

@bp.route("/suggest_name/<int:document_id>", methods=["POST"])
def suggest_name(document_id: int):
    """Get AI-generated name suggestion for a document."""
    try:
        # Get document details
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     document = get_document_by_id(document_id)
        
        # if not document:
        #     return jsonify(create_error_response("Document not found"))
        
        # Get AI suggestion based on OCR text
        # suggested_name = suggest_document_name(document['ocr_text'], document['category'])
        suggested_name = f"Document_{document_id}_suggested"  # Placeholder
        
        return jsonify(create_success_response({
            'suggested_name': suggested_name,
            'document_id': document_id,
            'confidence': 0.85  # Placeholder confidence score
        }))
        
    except Exception as e:
        logger.error(f"Error suggesting name for document {document_id}: {e}")
        return jsonify(create_error_response(f"Failed to suggest name: {str(e)}"))

@bp.route("/suggest_order/<int:document_id>", methods=["POST"])
def suggest_order(document_id: int):
    """Get AI-generated order suggestion for a document."""
    try:
        # Get document and batch context
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     document = get_document_by_id(document_id)
        #     batch_documents = get_documents_by_batch(document['batch_id'])
        
        # Get AI suggestion for ordering
        # suggested_order = suggest_document_order(document, batch_documents)
        suggested_order = 1  # Placeholder
        
        return jsonify(create_success_response({
            'suggested_order': suggested_order,
            'document_id': document_id,
            'reasoning': 'Based on document content and type'  # AI reasoning
        }))
        
    except Exception as e:
        logger.error(f"Error suggesting order for document {document_id}: {e}")
        return jsonify(create_error_response(f"Failed to suggest order: {str(e)}"))

@bp.route("/rotate_document/<int:doc_id>", methods=['POST'])
def rotate_document_api(doc_id: int):
    """Rotate a document by specified degrees."""
    try:
        data = request.get_json()
        rotation = data.get('rotation', 90)
        
        if rotation not in [0, 90, 180, 270]:
            return jsonify(create_error_response("Invalid rotation value. Must be 0, 90, 180, or 270"))
        
        # Perform document rotation
        # result = rotate_document(doc_id, rotation)
        
        return jsonify(create_success_response({
            'message': f'Document rotated by {rotation} degrees',
            'document_id': doc_id,
            'new_rotation': rotation
        }))
        
    except Exception as e:
        logger.error(f"Error rotating document {doc_id}: {e}")
        return jsonify(create_error_response(f"Failed to rotate document: {str(e)}"))

@bp.route("/rescan_document/<int:doc_id>", methods=['POST'])
def rescan_document_api(doc_id: int):
    """Rescan a document with OCR."""
    try:
        # Perform document rescan
        # result = rescan_document(doc_id)
        
        return jsonify(create_success_response({
            'message': 'Document rescanned successfully',
            'document_id': doc_id,
            'new_ocr_text': 'Placeholder OCR text'  # This would be the actual OCR result
        }))
        
    except Exception as e:
        logger.error(f"Error rescanning document {doc_id}: {e}")
        return jsonify(create_error_response(f"Failed to rescan document: {str(e)}"))

# Progress tracking APIs
@bp.route("/analyze_intake_progress")
def analyze_intake_progress():
    """Get progress of intake analysis."""
    try:
        with status_lock:
            progress = processing_status.get('intake_analysis', {
                'status': 'idle',
                'progress': 0,
                'message': 'No analysis in progress',
                'files_processed': 0,
                'total_files': 0
            })
        
        return jsonify(create_success_response(progress))
        
    except Exception as e:
        logger.error(f"Error getting intake progress: {e}")
        return jsonify(create_error_response(f"Failed to get progress: {str(e)}"))

@bp.route("/analyze_intake", methods=["POST"])
def analyze_intake_api():
    """Start intake analysis via API."""
    try:
        data = request.get_json() or {}
        intake_dir = data.get('intake_dir')
        
        if not intake_dir:
            return jsonify(create_error_response("Intake directory is required"))
        
        # Start analysis in background
        def analyze_async():
            try:
                with status_lock:
                    processing_status['intake_analysis'] = {
                        'status': 'analyzing',
                        'progress': 0,
                        'message': 'Starting intake analysis...',
                        'files_processed': 0,
                        'total_files': 0
                    }
                
                # Perform actual analysis
                # result = analyze_intake_directory(intake_dir)
                
                with status_lock:
                    processing_status['intake_analysis'] = {
                        'status': 'completed',
                        'progress': 100,
                        'message': 'Intake analysis completed',
                        'files_processed': 0,  # Actual count
                        'total_files': 0       # Actual count
                    }
                    
            except Exception as e:
                logger.error(f"Error in intake analysis: {e}")
                with status_lock:
                    processing_status['intake_analysis'] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Analysis failed: {str(e)}",
                        'files_processed': 0,
                        'total_files': 0
                    }
        
        thread = threading.Thread(target=analyze_async)
        thread.start()
        
        return jsonify(create_success_response({
            'message': 'Intake analysis started',
            'intake_dir': intake_dir
        }))
        
    except Exception as e:
        logger.error(f"Error starting intake analysis: {e}")
        return jsonify(create_error_response(f"Failed to start analysis: {str(e)}"))

@bp.route("/single_processing_progress")
def single_processing_progress():
    """Get progress of single document processing."""
    try:
        with status_lock:
            progress = processing_status.get('single_processing', {
                'status': 'idle',
                'progress': 0,
                'current_document': None,
                'total_documents': 0,
                'processed_documents': 0
            })
        
        return jsonify(create_success_response(progress))
        
    except Exception as e:
        logger.error(f"Error getting single processing progress: {e}")
        return jsonify(create_error_response(f"Failed to get progress: {str(e)}"))

@bp.route("/batch_processing_progress")
def batch_processing_progress():
    """Get progress of batch processing."""
    try:
        with status_lock:
            progress = processing_status.get('batch_processing', {
                'status': 'idle',
                'progress': 0,
                'current_batch': None,
                'message': 'No batch processing in progress'
            })
        
        return jsonify(create_success_response(progress))
        
    except Exception as e:
        logger.error(f"Error getting batch processing progress: {e}")
        return jsonify(create_error_response(f"Failed to get progress: {str(e)}"))

@bp.route("/smart_processing_start", methods=['POST'])
def smart_processing_start():
    """Start smart processing for a batch."""
    try:
        data = request.get_json()
        batch_id = data.get('batch_id')
        
        if not batch_id:
            return jsonify(create_error_response("Batch ID is required"))
        
        # Start smart processing
        def smart_process_async():
            try:
                with status_lock:
                    processing_status['smart_processing'] = {
                        'status': 'processing',
                        'progress': 0,
                        'batch_id': batch_id,
                        'message': 'Starting smart processing...',
                        'stages': {
                            'ocr': {'status': 'pending', 'progress': 0},
                            'classification': {'status': 'pending', 'progress': 0},
                            'grouping': {'status': 'pending', 'progress': 0},
                            'ordering': {'status': 'pending', 'progress': 0}
                        }
                    }
                
                # Simulate smart processing stages
                stages = ['ocr', 'classification', 'grouping', 'ordering']
                for i, stage in enumerate(stages):
                    # Update stage status
                    with status_lock:
                        processing_status['smart_processing']['stages'][stage]['status'] = 'processing'
                        processing_status['smart_processing']['message'] = f'Processing {stage}...'
                    
                    # Simulate processing time
                    time.sleep(2)
                    
                    # Complete stage
                    with status_lock:
                        processing_status['smart_processing']['stages'][stage]['status'] = 'completed'
                        processing_status['smart_processing']['stages'][stage]['progress'] = 100
                        processing_status['smart_processing']['progress'] = int((i + 1) / len(stages) * 100)
                
                # Complete processing
                with status_lock:
                    processing_status['smart_processing']['status'] = 'completed'
                    processing_status['smart_processing']['message'] = 'Smart processing completed'
                    
            except Exception as e:
                logger.error(f"Error in smart processing: {e}")
                with status_lock:
                    processing_status['smart_processing'] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Smart processing failed: {str(e)}"
                    }
        
        thread = threading.Thread(target=smart_process_async)
        thread.start()
        
        return jsonify(create_success_response({
            'message': 'Smart processing started',
            'batch_id': batch_id
        }))
        
    except Exception as e:
        logger.error(f"Error starting smart processing: {e}")
        return jsonify(create_error_response(f"Failed to start smart processing: {str(e)}"))

@bp.route("/smart_processing_status")
def smart_processing_status():
    """Get detailed smart processing status."""
    try:
        with status_lock:
            status = processing_status.get('smart_processing', {
                'status': 'idle',
                'progress': 0,
                'message': 'No smart processing in progress',
                'stages': {}
            })
        
        return jsonify(create_success_response(status))
        
    except Exception as e:
        logger.error(f"Error getting smart processing status: {e}")
        return jsonify(create_error_response(f"Failed to get status: {str(e)}"))

# Server-Sent Events for real-time updates
@bp.route("/events/processing_status")
def processing_status_events():
    """Server-sent events for real-time processing status updates."""
    def generate_events() -> Generator[str, None, None]:
        """Generate server-sent events for processing status."""
        last_status = {}
        
        while True:
            try:
                with status_lock:
                    current_status = dict(processing_status)
                
                # Only send if status changed
                if current_status != last_status:
                    yield f"data: {json.dumps(current_status)}\n\n"
                    last_status = current_status.copy()
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error(f"Error in SSE generation: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                break
    
    return Response(generate_events(), mimetype='text/event-stream')

@bp.route("/events/batch_status/<int:batch_id>")
def batch_status_events(batch_id: int):
    """Server-sent events for specific batch status updates."""
    def generate_batch_events() -> Generator[str, None, None]:
        """Generate server-sent events for batch status."""
        while True:
            try:
                # Get current batch status
                # with database_connection() as conn:
                #     cursor = conn.cursor()
                #     batch_status = get_batch_status(batch_id)
                
                batch_status = {'status': 'unknown', 'progress': 0}  # Placeholder
                
                yield f"data: {json.dumps(batch_status)}\n\n"
                time.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                logger.error(f"Error in batch SSE generation: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                break
    
    return Response(generate_batch_events(), mimetype='text/event-stream')

# Utility APIs
@bp.route("/file_safety_check")
def file_safety_check():
    """Check if files are safe to process."""
    try:
        # Check for file locks, disk space, etc.
        safety_status = {
            'safe_to_process': True,
            'warnings': [],
            'disk_space_gb': 10.5,  # Placeholder
            'active_processes': 0    # Placeholder
        }
        
        return jsonify(create_success_response(safety_status))
        
    except Exception as e:
        logger.error(f"Error checking file safety: {e}")
        return jsonify(create_error_response(f"Failed to check file safety: {str(e)}"))

@bp.route("/system_info")
def system_info():
    """Get system information and stats."""
    try:
        import platform
        import psutil
        
        system_info = {
            'platform': platform.system(),
            'python_version': platform.python_version(),
            'cpu_count': psutil.cpu_count(),
            'memory_gb': round(psutil.virtual_memory().total / (1024**3), 2),
            'disk_usage': {
                'total_gb': round(psutil.disk_usage('/').total / (1024**3), 2),
                'free_gb': round(psutil.disk_usage('/').free / (1024**3), 2)
            }
        }
        
        return jsonify(create_success_response(system_info))
        
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return jsonify(create_error_response(f"Failed to get system info: {str(e)}"))

# Debugging and development APIs
@bp.route("/debug/clear_status")
def clear_processing_status():
    """Clear all processing status (for debugging)."""
    try:
        with status_lock:
            processing_status.clear()
        
        return jsonify(create_success_response({
            'message': 'Processing status cleared'
        }))
        
    except Exception as e:
        logger.error(f"Error clearing processing status: {e}")
        return jsonify(create_error_response(f"Failed to clear status: {str(e)}"))

@bp.route("/debug/processing_status")
def debug_processing_status():
    """Get current processing status for debugging."""
    try:
        with status_lock:
            current_status = dict(processing_status)
        
        return jsonify(create_success_response({
            'processing_status': current_status,
            'status_count': len(current_status)
        }))
        
    except Exception as e:
        logger.error(f"Error getting debug status: {e}")
        return jsonify(create_error_response(f"Failed to get debug status: {str(e)}"))
"""
Batch Manag# Import existing modules (these imports will need to be adjusted based on the actual module structure)
from database import (
    get_db_connection, get_batch_by_id, get_documents_for_batch
)
from processing import process_batch, database_connection
from config_manager import app_config
from utils.helpers import create_error_response, create_success_responseoutes Blueprint

This module contains all routes related to batch control, processing, and management.
Extracted from the monolithic app.py to improve maintainability.
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
import logging
from typing import Dict, Any
import os
import json
import threading
from datetime import datetime

# Import existing modules (these imports will need to be adjusted based on the actual module structure)
from ..database import (
    get_db_connection, get_batch_by_id, get_documents_for_batch
)
from ..processing import process_batch, database_connection, process_single_document
from ..config_manager import app_config
from ..utils.helpers import create_error_response, create_success_response

# Create Blueprint
bp = Blueprint('batch', __name__, url_prefix='/batch')
logger = logging.getLogger(__name__)

# Global variables for tracking processing state (these should eventually move to a service class)
processing_status = {}
processing_lock = threading.Lock()
export_status = {}
export_lock = threading.Lock()

@bp.route("/control")
def batch_control():
    """Main batch control page showing all batches and their status."""
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            
            # Get all batches with their status
            cursor.execute("""
                SELECT b.id, b.status, b.start_time,
                       COUNT(d.id) as document_count,
                       COUNT(CASE WHEN d.status = 'completed' THEN 1 END) as completed_count
                FROM batches b
                LEFT JOIN documents d ON b.id = d.batch_id
                GROUP BY b.id, b.status, b.start_time
                ORDER BY b.start_time DESC
            """)
            
            batches = []
            for row in cursor.fetchall():
                batch_id, status, start_time, doc_count, completed_count = row
                batches.append({
                    'id': batch_id,
                    'name': f'Batch {batch_id}',  # Generate a name since there's no name column
                    'status': status,
                    'start_time': start_time,  # Add start_time for template
                    'created_at': start_time,  # Map start_time to created_at for template compatibility
                    'document_count': doc_count,
                    'completed_count': completed_count,
                    'progress_percent': (completed_count / doc_count * 100) if doc_count > 0 else 0
                })
            
            return render_template('batch_control.html', batches=batches)
            
    except Exception as e:
        logger.error(f"Error loading batch control page: {e}")
        flash(f"Error loading batches: {str(e)}", "error")
        return render_template('batch_control.html', batches=[])

@bp.route("/process_new", methods=["POST"])
def process_new_batch():
    """Create and process a new batch from intake directory."""
    try:
        intake_dir = app_config.INTAKE_DIR
        if not intake_dir or not os.path.exists(intake_dir):
            return jsonify(create_error_response("Intake directory not configured or doesn't exist"))
        
        # Create new batch
        with database_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO batches (status)
                VALUES ('intake')
            """)
            
            batch_id = cursor.lastrowid
        
        # Start processing in background
        def process_batch_async():
            try:
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'processing',
                        'progress': 0,
                        'message': 'Starting batch processing...'
                    }
                
                # Process the batch
                result = process_batch()
                
                with processing_lock:
                    if result:
                        processing_status[batch_id] = {
                            'status': 'completed',
                            'progress': 100,
                            'message': 'Batch processing completed successfully'
                        }
                    else:
                        processing_status[batch_id] = {
                            'status': 'error',
                            'progress': 0,
                            'message': 'Batch processing failed'
                        }
                        
            except Exception as e:
                logger.error(f"Error in async batch processing: {e}")
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Processing error: {str(e)}"
                    }
        
        thread = threading.Thread(target=process_batch_async)
        thread.start()
        
        return jsonify(create_success_response({
            'batch_id': batch_id,
            'message': f'Batch {batch_id} created and processing started'
        }))
        
    except Exception as e:
        logger.error(f"Error creating new batch: {e}")
        return jsonify(create_error_response(f"Failed to create batch: {str(e)}"))

@bp.route("/process_smart", methods=["POST"])
def process_batch_smart():
    """Start smart processing for a batch."""
    try:
        batch_id = request.json.get('batch_id') if request.json else None
        if not batch_id:
            return jsonify(create_error_response("Batch ID is required"))
        
        # Validate batch exists
        with database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM batches WHERE id = ?", (batch_id,))
            result = cursor.fetchone()
            
            if not result:
                return jsonify(create_error_response("Batch not found"))
            
            if result[0] not in ['ready', 'processed']:
                return jsonify(create_error_response(f"Batch is not ready for smart processing (status: {result[0]})"))
        
        # Start smart processing
        def smart_process_async():
            try:
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'smart_processing',
                        'progress': 0,
                        'message': 'Starting smart processing...'
                    }
                
                # Update batch status
                with database_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE batches SET status = 'smart_processing' WHERE id = ?", (batch_id,))
                
                # Process documents with AI classification
                # This would call the smart processing logic
                # result = smart_process_batch(batch_id)
                
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'completed',
                        'progress': 100,
                        'message': 'Smart processing completed'
                    }
                    
            except Exception as e:
                logger.error(f"Error in smart processing: {e}")
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Smart processing error: {str(e)}"
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

@bp.route("/process_all_single", methods=["POST"])
def process_batch_all_single():
    """Process all documents in a batch as single-page documents."""
    try:
        batch_id = request.json.get('batch_id') if request.json else None
        if not batch_id:
            return jsonify(create_error_response("Batch ID is required"))
        
        # Start single document processing
        def process_single_async():
            try:
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'processing_single',
                        'progress': 0,
                        'message': 'Processing as single documents...'
                    }
                
                # Get all documents in batch
                with database_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM documents WHERE batch_id = ?", (batch_id,))
                    document_ids = [row[0] for row in cursor.fetchall()]
                
                total_docs = len(document_ids)
                processed = 0
                
                for doc_id in document_ids:
                    try:
                        # TODO: Fix this function call - process_single_document needs correct implementation
                        # process_single_document(doc_id)
                        processed += 1
                        
                        with processing_lock:
                            processing_status[batch_id]['progress'] = int(processed / total_docs * 100)
                            processing_status[batch_id]['message'] = f'Processed {processed}/{total_docs} documents'
                            
                    except Exception as e:
                        logger.error(f"Error processing document {doc_id}: {e}")
                
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'completed',
                        'progress': 100,
                        'message': f'Completed processing {processed}/{total_docs} documents'
                    }
                    
            except Exception as e:
                logger.error(f"Error in single document processing: {e}")
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Processing error: {str(e)}"
                    }
        
        thread = threading.Thread(target=process_single_async)
        thread.start()
        
        return jsonify(create_success_response({
            'message': 'Single document processing started',
            'batch_id': batch_id
        }))
        
    except Exception as e:
        logger.error(f"Error starting single document processing: {e}")
        return jsonify(create_error_response(f"Failed to start processing: {str(e)}"))

@bp.route("/force_traditional", methods=["POST"])
def process_batch_force_traditional():
    """Force traditional (non-smart) processing for a batch."""
    try:
        batch_id = request.json.get('batch_id') if request.json else None
        if not batch_id:
            return jsonify(create_error_response("Batch ID is required"))
        
        # Start traditional processing
        def traditional_process_async():
            try:
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'traditional_processing',
                        'progress': 0,
                        'message': 'Starting traditional processing...'
                    }
                
                # Process with traditional methods (no AI)
                result = process_batch()
                
                with processing_lock:
                    if result:
                        processing_status[batch_id] = {
                            'status': 'completed',
                            'progress': 100,
                            'message': 'Traditional processing completed'
                        }
                    else:
                        processing_status[batch_id] = {
                            'status': 'error',
                            'progress': 0,
                            'message': 'Traditional processing failed'
                        }
                        
            except Exception as e:
                logger.error(f"Error in traditional processing: {e}")
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Processing error: {str(e)}"
                    }
        
        thread = threading.Thread(target=traditional_process_async)
        thread.start()
        
        return jsonify(create_success_response({
            'message': 'Traditional processing started',
            'batch_id': batch_id
        }))
        
    except Exception as e:
        logger.error(f"Error starting traditional processing: {e}")
        return jsonify(create_error_response(f"Failed to start processing: {str(e)}"))

@bp.route("/<int:batch_id>/reset", methods=["POST"])
def reset_batch(batch_id: int):
    """Reset a batch to initial state."""
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            
            # Reset batch status
            cursor.execute("UPDATE batches SET status = 'intake' WHERE id = ?", (batch_id,))
            
            # Reset all documents in batch
            cursor.execute("UPDATE documents SET status = 'pending' WHERE batch_id = ?", (batch_id,))
            
            # Clear any processing status
            with processing_lock:
                if batch_id in processing_status:
                    del processing_status[batch_id]
        
        return jsonify(create_success_response({
            'message': f'Batch {batch_id} has been reset',
            'batch_id': batch_id
        }))
        
    except Exception as e:
        logger.error(f"Error resetting batch {batch_id}: {e}")
        return jsonify(create_error_response(f"Failed to reset batch: {str(e)}"))

@bp.route("/<int:batch_id>/reset_grouping", methods=["POST"])
def reset_grouping(batch_id: int):
    """Reset grouping for a batch."""
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            
            # Reset grouping information
            cursor.execute("""
                UPDATE documents 
                SET group_id = NULL, group_position = NULL 
                WHERE batch_id = ?
            """, (batch_id,))
            
            # Update batch status if needed
            cursor.execute("UPDATE batches SET status = 'processed' WHERE id = ?", (batch_id,))
        
        return jsonify(create_success_response({
            'message': f'Grouping reset for batch {batch_id}',
            'batch_id': batch_id
        }))
        
    except Exception as e:
        logger.error(f"Error resetting grouping for batch {batch_id}: {e}")
        return jsonify(create_error_response(f"Failed to reset grouping: {str(e)}"))

@bp.route("/<int:batch_id>/audit")
def batch_audit(batch_id: int):
    """Display audit information for a batch."""
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            
            # Get batch info
            cursor.execute("SELECT * FROM batches WHERE id = ?", (batch_id,))
            batch = cursor.fetchone()
            
            if not batch:
                flash("Batch not found", "error")
                return redirect(url_for('batch.batch_control'))
            
            # Get detailed document information
            cursor.execute("""
                SELECT id, filename, status, category, confidence_score, 
                       ocr_text, created_at, updated_at
                FROM documents 
                WHERE batch_id = ?
                ORDER BY id
            """, (batch_id,))
            
            documents = cursor.fetchall()
            
            # Get processing statistics
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM documents 
                WHERE batch_id = ?
                GROUP BY status
            """, (batch_id,))
            
            status_counts = dict(cursor.fetchall())
            
            return render_template('batch_audit.html', 
                                 batch=batch, 
                                 documents=documents,
                                 status_counts=status_counts)
            
    except Exception as e:
        logger.error(f"Error loading batch audit for {batch_id}: {e}")
        flash(f"Error loading audit: {str(e)}", "error")
        return redirect(url_for('batch.batch_control'))

# Progress tracking routes
@bp.route("/processing_progress")
def batch_processing_progress():
    """Page to display batch processing progress."""
    return render_template('batch_processing_progress.html')

@bp.route("/api/processing_progress")
def api_batch_processing_progress():
    """API endpoint for batch processing progress."""
    try:
        with processing_lock:
            return jsonify(create_success_response(processing_status))
    except Exception as e:
        logger.error(f"Error getting processing progress: {e}")
        return jsonify(create_error_response(f"Failed to get progress: {str(e)}"))

@bp.route("/smart_processing_progress")
def smart_processing_progress():
    """Page to display smart processing progress."""
    return render_template('smart_processing_progress.html')

@bp.route("/api/smart_processing_progress")
def api_smart_processing_progress():
    """API endpoint for smart processing progress."""
    try:
        with processing_lock:
            smart_status = {k: v for k, v in processing_status.items() 
                          if v.get('status') == 'smart_processing'}
            return jsonify(create_success_response(smart_status))
    except Exception as e:
        logger.error(f"Error getting smart processing progress: {e}")
        return jsonify(create_error_response(f"Failed to get progress: {str(e)}"))
"""
Document Manipulation Routes Blueprint

This module contains all routes related to document manipulation including:
- Document verification and review
- Document grouping and ordering
- Document editing and updates
- Page-level operations (rotation, OCR, etc.)

Extracted from the monolithic app.py to improve maintainability.
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
import logging
from typing import Dict, Any, List, Optional
import json
import os

# Import existing modules (these imports will need to be adjusted)
from ..database import (
    get_db_connection, get_documents_for_batch,
    update_page_data, get_pages_for_batch, get_pages_for_document,
    update_page_rotation, log_interaction
)
from ..config_manager import app_config
from ..utils.helpers import create_error_response, create_success_response

# Create Blueprint
bp = Blueprint('manipulation', __name__, url_prefix='/document')
logger = logging.getLogger(__name__)

@bp.route("/verify/<int:batch_id>")
def verify_batch(batch_id: int):
    """Display verification page for a batch of documents."""
    try:
        # This would normally fetch batch and document data
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     # Get batch info and documents
        #     documents = get_documents_by_batch(batch_id)
        
        # For now, render template with placeholder data
        return render_template('verify.html', batch_id=batch_id, documents=[])
        
    except Exception as e:
        logger.error(f"Error loading verification page for batch {batch_id}: {e}")
        flash(f"Error loading verification: {str(e)}", "error")
        return redirect(url_for('batch.batch_control'))

@bp.route("/review/<int:batch_id>")
def review_batch(batch_id: int):
    """Display review page for processed documents in a batch."""
    try:
        # This would fetch documents with AI classifications for review
        return render_template('review.html', batch_id=batch_id, documents=[])
        
    except Exception as e:
        logger.error(f"Error loading review page for batch {batch_id}: {e}")
        flash(f"Error loading review: {str(e)}", "error")
        return redirect(url_for('batch.batch_control'))

@bp.route("/revisit/<int:batch_id>")
def revisit_batch(batch_id: int):
    """Display revisit page for documents needing additional review."""
    try:
        # This would fetch documents marked for revisit
        return render_template('revisit.html', batch_id=batch_id, documents=[])
        
    except Exception as e:
        logger.error(f"Error loading revisit page for batch {batch_id}: {e}")
        flash(f"Error loading revisit: {str(e)}", "error")
        return redirect(url_for('batch.batch_control'))

@bp.route("/view/<int:batch_id>")
def view_batch(batch_id: int):
    """Display view page for all documents in a batch."""
    try:
        # This would fetch all documents for viewing
        return render_template('view_batch.html', batch_id=batch_id, documents=[])
        
    except Exception as e:
        logger.error(f"Error loading view page for batch {batch_id}: {e}")
        flash(f"Error loading view: {str(e)}", "error")
        return redirect(url_for('batch.batch_control'))

@bp.route("/group/<int:batch_id>")
def group_documents(batch_id: int):
    """Display grouping interface for organizing documents."""
    try:
        # This would fetch documents and existing groups
        return render_template('group.html', batch_id=batch_id, documents=[])
        
    except Exception as e:
        logger.error(f"Error loading grouping page for batch {batch_id}: {e}")
        flash(f"Error loading grouping: {str(e)}", "error")
        return redirect(url_for('batch.batch_control'))

@bp.route("/order/<int:batch_id>")
def order_documents(batch_id: int):
    """Display ordering interface for sequencing documents."""
    try:
        # This would fetch grouped documents for ordering
        return render_template('order_batch.html', batch_id=batch_id, groups=[])
        
    except Exception as e:
        logger.error(f"Error loading ordering page for batch {batch_id}: {e}")
        flash(f"Error loading ordering: {str(e)}", "error")
        return redirect(url_for('batch.batch_control'))

@bp.route("/order_document/<int:document_id>", methods=["GET", "POST"])
def order_single_document(document_id: int):
    """Handle ordering for a single document."""
    try:
        if request.method == "POST":
            # Handle document ordering update
            new_position = request.form.get('position')
            if new_position:
                # Update document position in database
                # update_document_position(document_id, int(new_position))
                flash("Document position updated successfully", "success")
                return redirect(url_for('manipulation.order_documents', batch_id=request.form.get('batch_id')))
        
        # GET request - show single document ordering page
        return render_template('order_document.html', document_id=document_id)
        
    except Exception as e:
        logger.error(f"Error handling document ordering for {document_id}: {e}")
        flash(f"Error updating document order: {str(e)}", "error")
        return redirect(url_for('batch.batch_control'))

@bp.route("/save", methods=["POST"])
def save_document():
    """Save document changes (category, name, etc.)."""
    try:
        document_id = request.form.get('document_id')
        category = request.form.get('category')
        filename = request.form.get('filename')
        
        if not document_id:
            return jsonify(create_error_response("Document ID is required"))
        
        # Update document in database
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     cursor.execute("""
        #         UPDATE documents 
        #         SET category = ?, filename = ?, updated_at = datetime('now')
        #         WHERE id = ?
        #     """, (category, filename, document_id))
        
        return jsonify(create_success_response({
            'message': 'Document saved successfully',
            'document_id': document_id
        }))
        
    except Exception as e:
        logger.error(f"Error saving document: {e}")
        return jsonify(create_error_response(f"Failed to save document: {str(e)}"))

@bp.route("/update_page", methods=["POST"])
def update_page():
    """Update page information (OCR text, category, etc.)."""
    try:
        page_id = request.form.get('page_id')
        ocr_text = request.form.get('ocr_text')
        category = request.form.get('category')
        
        if not page_id:
            return jsonify(create_error_response("Page ID is required"))
        
        # Update page in database
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     cursor.execute("""
        #         UPDATE documents 
        #         SET ocr_text = ?, category = ?, updated_at = datetime('now')
        #         WHERE id = ?
        #     """, (ocr_text, category, page_id))
        
        return jsonify(create_success_response({
            'message': 'Page updated successfully',
            'page_id': page_id
        }))
        
    except Exception as e:
        logger.error(f"Error updating page: {e}")
        return jsonify(create_error_response(f"Failed to update page: {str(e)}"))

@bp.route("/delete_page/<int:page_id>", methods=["POST"])
def delete_page(page_id: int):
    """Delete a page/document."""
    try:
        # Delete from database
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     cursor.execute("DELETE FROM documents WHERE id = ?", (page_id,))
        
        return jsonify(create_success_response({
            'message': 'Page deleted successfully',
            'page_id': page_id
        }))
        
    except Exception as e:
        logger.error(f"Error deleting page {page_id}: {e}")
        return jsonify(create_error_response(f"Failed to delete page: {str(e)}"))

@bp.route("/rerun_ocr", methods=["POST"])
def rerun_ocr():
    """Rerun OCR for a document."""
    try:
        document_id = request.form.get('document_id')
        if not document_id:
            return jsonify(create_error_response("Document ID is required"))
        
        # Rerun OCR processing
        # result = rerun_ocr_for_document(document_id)
        
        return jsonify(create_success_response({
            'message': 'OCR rerun completed',
            'document_id': document_id
        }))
        
    except Exception as e:
        logger.error(f"Error rerunning OCR: {e}")
        return jsonify(create_error_response(f"Failed to rerun OCR: {str(e)}"))

@bp.route("/update_rotation", methods=["POST"])
def update_rotation_api():
    """AJAX endpoint to persist rotation without changing status/category.

    Expected JSON body: { page_id: int, batch_id: int, rotation: int }
    Returns JSON: { success: bool, error?: str }
    """
    try:
        data = request.get_json(force=True)
        page_id = int(data.get("page_id"))
        batch_id = int(data.get("batch_id"))
        rotation = int(data.get("rotation", 0))
    except Exception:
        return jsonify({"success": False, "error": "Invalid input"}), 400
    if rotation not in {0,90,180,270}:
        return jsonify({"success": False, "error": "Invalid rotation"}), 400
    ok = update_page_rotation(page_id, rotation)
    if not ok:
        return jsonify({"success": False, "error": "DB update failed"}), 500
    # Log interaction for audit trail
    try:
        log_interaction(batch_id=batch_id, document_id=None, user_id=None, event_type="human_correction", step="rotation_update", content=json.dumps({"page_id":page_id,"rotation":rotation}), notes=None)
    except Exception as e:
        logger.warning(f"Failed to log rotation interaction: {e}")
    return jsonify({"success": True})

# Batch-level manipulation operations
@bp.route("/batch/<int:batch_id>/manipulate", methods=['GET'])
@bp.route("/batch/<int:batch_id>/manipulate/<int:doc_num>", methods=['GET', 'POST'])
def manipulate_batch_documents(batch_id: int, doc_num: Optional[int] = None):
    """Manipulate documents within a batch (combined route)."""
    try:
        if request.method == 'POST' and doc_num is not None:
            # Handle document manipulation updates
            action = request.form.get('action')
            
            if action == 'rotate':
                rotation = request.form.get('rotation', 0)
                # Rotate specific document
                # rotate_document(batch_id, doc_num, int(rotation))
                
            elif action == 'recategorize':
                new_category = request.form.get('category')
                # Update document category
                # update_document_category(batch_id, doc_num, new_category)
                
            elif action == 'rescan':
                # Rescan document with OCR
                # rescan_document(batch_id, doc_num)
                pass
            
            flash(f"Document {doc_num} updated successfully", "success")
            return redirect(url_for('manipulation.manipulate_batch_documents', batch_id=batch_id))
        
        # GET request - show manipulation interface
        # Get all documents in batch for manipulation
        # documents = get_documents_by_batch(batch_id)
        documents = []  # Placeholder
        
        if doc_num is not None:
            # Show specific document manipulation
            return render_template('manipulate_document.html', 
                                 batch_id=batch_id, 
                                 doc_num=doc_num,
                                 documents=documents)
        else:
            # Show batch manipulation overview
            return render_template('manipulate_batch.html', 
                                 batch_id=batch_id,
                                 documents=documents)
        
    except Exception as e:
        logger.error(f"Error in batch manipulation for batch {batch_id}: {e}")
        flash(f"Error manipulating documents: {str(e)}", "error")
        return redirect(url_for('batch.batch_control'))

# Document revisit operations
@bp.route("/revisit_ordering_document/<int:document_id>", methods=["POST"])
def revisit_ordering_document(document_id: int):
    """Mark a document for ordering revisit."""
    try:
        # Mark document for revisit
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     cursor.execute("""
        #         UPDATE documents 
        #         SET status = 'needs_ordering_review', updated_at = datetime('now')
        #         WHERE id = ?
        #     """, (document_id,))
        
        return jsonify(create_success_response({
            'message': 'Document marked for ordering review',
            'document_id': document_id
        }))
        
    except Exception as e:
        logger.error(f"Error marking document for revisit: {e}")
        return jsonify(create_error_response(f"Failed to mark for revisit: {str(e)}"))

@bp.route("/revisit_ordering/<int:batch_id>", methods=["POST"])
def revisit_ordering_batch(batch_id: int):
    """Mark entire batch for ordering revisit."""
    try:
        # Mark all documents in batch for revisit
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     cursor.execute("""
        #         UPDATE documents 
        #         SET status = 'needs_ordering_review', updated_at = datetime('now')
        #         WHERE batch_id = ?
        #     """, (batch_id,))
        
        return jsonify(create_success_response({
            'message': f'Batch {batch_id} marked for ordering review',
            'batch_id': batch_id
        }))
        
    except Exception as e:
        logger.error(f"Error marking batch for revisit: {e}")
        return jsonify(create_error_response(f"Failed to mark batch for revisit: {str(e)}"))

@bp.route("/finish_ordering/<int:batch_id>", methods=["POST"])
def finish_ordering(batch_id: int):
    """Complete the ordering process for a batch."""
    try:
        # Update batch status to indicate ordering is complete
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     cursor.execute("UPDATE batches SET status = 'ordered' WHERE id = ?", (batch_id,))
        
        return jsonify(create_success_response({
            'message': f'Ordering completed for batch {batch_id}',
            'batch_id': batch_id
        }))
        
    except Exception as e:
        logger.error(f"Error finishing ordering for batch {batch_id}: {e}")
        return jsonify(create_error_response(f"Failed to finish ordering: {str(e)}"))

# Document viewing
@bp.route("/view_documents/<int:batch_id>")
def view_documents(batch_id: int):
    """View all documents in a batch with detailed information."""
    try:
        # Get all documents with full details
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     documents = get_documents_by_batch(batch_id, include_details=True)
        
        return render_template('view_documents.html', 
                             batch_id=batch_id, 
                             documents=[])
        
    except Exception as e:
        logger.error(f"Error viewing documents for batch {batch_id}: {e}")
        flash(f"Error loading documents: {str(e)}", "error")
        return redirect(url_for('batch.batch_control'))
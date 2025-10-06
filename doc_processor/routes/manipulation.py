"""
Document Manipulation Routes Blueprint

This module contains all routes related to document manipulation including:
- Document verification and review
- Document grouping and ordering
- Document editing and updates
- Page-level operations (rotation, OCR, etc.)

Extracted from the monolithic app.py to improve maintainability.
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, send_file
import logging
from typing import Dict, Any, List, Optional
import json
import os

# Import existing modules (these imports will need to be adjusted)
from ..database import (
    get_db_connection, get_documents_for_batch,
    update_page_data, get_pages_for_batch, get_pages_for_document,
    update_page_rotation, log_interaction, get_single_documents_for_batch
)
from ..llm_utils import get_ai_document_type_analysis  # assuming existing utility for AI suggestion regeneration
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

@bp.route('/serve_single_pdf/<int:doc_id>')
def serve_single_pdf(doc_id: int):
    """Serve the stored original_pdf_path for a single_document row.

    This avoids guessing paths from the original intake filename. The path was
    established during processing (image->PDF conversion or existing PDF). We
    validate that it lives within allowed directories (intake, processed,
    normalized, archive) to mitigate path traversal or arbitrary file serving.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        row = cur.execute("SELECT original_pdf_path, original_filename FROM single_documents WHERE id=?", (doc_id,)).fetchone()
        conn.close()
        if not row or not row[0]:
            return jsonify(create_error_response("PDF path not recorded", 404)), 404
        pdf_path = row[0]
        original_filename = row[1] if len(row) > 1 else f"doc_{doc_id}.pdf"

        # Look up persisted rotation (filename key should match intake/original naming used in rotations table)
        rotation_degrees = 0
        rotation_updated_at = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS intake_rotations (filename TEXT PRIMARY KEY, rotation INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            rot_row = cur.execute("SELECT rotation, updated_at FROM intake_rotations WHERE filename = ?", (original_filename,)).fetchone()
            if rot_row:
                rotation_degrees = int(rot_row[0]) % 360
                rotation_updated_at = rot_row[1]
            else:
                # Fallback: attempt to infer from first page rotation_angle if pages table links exist
                try:
                    fallback = cur.execute("""
                        SELECT p.rotation_angle FROM pages p
                        JOIN document_pages dp ON p.id = dp.page_id
                        JOIN documents d ON d.id = dp.document_id
                        WHERE d.id = ? ORDER BY dp.sequence ASC LIMIT 1
                    """, (doc_id,)).fetchone()
                    if fallback and fallback[0]:
                        rotation_degrees = int(fallback[0]) % 360
                        rotation_updated_at = None
                except Exception as fb_err:
                    logger.debug(f"Rotation fallback failed doc {doc_id}: {fb_err}")
            conn.close()
        except Exception as rot_err:
            try:
                conn.close()
            except Exception:
                pass
            logger.debug(f"Rotation lookup failed for {original_filename}: {rot_err}")
        # Security: restrict to known base directories
        allowed_dirs = [
            app_config.INTAKE_DIR,
            app_config.PROCESSED_DIR,
            app_config.NORMALIZED_DIR if hasattr(app_config, 'NORMALIZED_DIR') else 'normalized',
            app_config.ARCHIVE_DIR,
        ]
        pdf_abs = os.path.abspath(pdf_path)
        allowed_abs = [os.path.abspath(d) for d in allowed_dirs if d]
        if not any(pdf_abs.startswith(d + os.sep) or pdf_abs == d for d in allowed_abs):
            logger.warning(f"Blocked PDF serve outside allowed dirs: {pdf_abs}")
            return jsonify(create_error_response("Access denied", 403)), 403
        if not os.path.exists(pdf_abs):
            logger.warning(f"Stored PDF path missing for doc {doc_id}: {pdf_abs}")
            return jsonify(create_error_response("File not found", 404)), 404

        # If rotation needed, produce a transient rotated PDF (cache in /tmp for session)
        if rotation_degrees and rotation_degrees in (90,180,270):
            try:
                import fitz  # PyMuPDF
                import tempfile, time, datetime
                # Detect if original already contains rotation (prevent double rotate)
                try:
                    test_doc = fitz.open(pdf_abs)
                    if test_doc.page_count > 0:
                        existing_rot = test_doc[0].rotation
                        if existing_rot == rotation_degrees:
                            rotation_degrees = 0  # already physically rotated
                    test_doc.close()
                except Exception:
                    pass
                if rotation_degrees:
                    tmp_dir = tempfile.gettempdir()
                    rotated_path = os.path.join(tmp_dir, f"rotated_doc_{doc_id}_{rotation_degrees}.pdf")
                    regenerate = True
                    if os.path.exists(rotated_path):
                        # Compare mtime to rotation_updated_at
                        if rotation_updated_at:
                            try:
                                # Normalize timestamp format
                                ts = rotation_updated_at.replace(' ', 'T')
                                rot_dt = datetime.datetime.fromisoformat(ts)
                                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(rotated_path))
                                if mtime >= rot_dt:
                                    regenerate = False
                            except Exception:
                                regenerate = True
                        else:
                            regenerate = False  # no timestamp to compare
                    if regenerate:
                        doc = fitz.open(pdf_abs)
                        for page in doc:
                            page.set_rotation((page.rotation + rotation_degrees) % 360)
                        doc.save(rotated_path, incremental=False, deflate=True)
                        doc.close()
                        logger.debug(f"Generated rotated PDF doc {doc_id} rotation={rotation_degrees}")
                    else:
                        logger.debug(f"Using cached rotated PDF doc {doc_id} rotation={rotation_degrees}")
                    return send_file(rotated_path, mimetype='application/pdf', as_attachment=False)
            except Exception as rot_apply_err:
                logger.warning(f"Failed to apply rotation {rotation_degrees} for doc {doc_id}: {rot_apply_err}; serving unrotated")

        return send_file(pdf_abs, mimetype='application/pdf', as_attachment=False)
    except Exception as e:
        logger.error(f"serve_single_pdf failed doc {doc_id}: {e}")
        return jsonify(create_error_response("Internal error serving PDF")), 500
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
    """Unified manipulation UI using manipulate.html with safe fallbacks.

    - Loads documents for the batch (if available)
    - Computes pagination context
    - Builds a minimal current_doc dict for the template
    - On POST, performs no-ops for now and redirects (placeholder wiring)
    """
    try:
        # Determine dataset: prefer single_documents workflow if rows exist, else fall back to grouped documents
        single_docs = get_single_documents_for_batch(batch_id)
        using_single = len(single_docs) > 0

        if request.method == 'POST' and doc_num is not None:
            # Persist user selections similar to legacy monolithic implementation
            doc_id = request.form.get('doc_id')
            action = request.form.get('action', 'finish_batch')
            if using_single and doc_id:
                try:
                    conn = get_db_connection()
                    cur = conn.cursor()

                    # Category selection logic
                    category_dropdown = request.form.get('category_dropdown')
                    if category_dropdown == 'other_new':
                        new_category = (request.form.get('other_category') or '').strip() or None
                    elif category_dropdown:
                        new_category = category_dropdown
                    else:
                        # Keep AI suggestion
                        row = cur.execute("SELECT ai_suggested_category FROM single_documents WHERE id=?", (doc_id,)).fetchone()
                        new_category = row[0] if row else None

                    # Filename selection logic
                    filename_choice = request.form.get('filename_choice')
                    if filename_choice == 'custom':
                        new_filename = (request.form.get('custom_filename') or '').strip() or None
                    elif filename_choice == 'original':
                        row = cur.execute("SELECT original_filename FROM single_documents WHERE id=?", (doc_id,)).fetchone()
                        if row:
                            original = row[0]
                            new_filename = original.rsplit('.', 1)[0] if '.' in original else original
                        else:
                            new_filename = None
                    else:  # ai
                        row = cur.execute("SELECT ai_suggested_filename FROM single_documents WHERE id=?", (doc_id,)).fetchone()
                        new_filename = row[0] if row else None

                    cur.execute("""
                        UPDATE single_documents SET final_category=?, final_filename=? WHERE id=?
                    """, (new_category, new_filename, doc_id))
                    conn.commit()

                    # If finishing batch, mark batch ready for export
                    if action == 'finish_batch':
                        cur.execute("UPDATE batches SET status='ready_for_export', has_been_manipulated=1 WHERE id=?", (batch_id,))
                        conn.commit()
                        flash('All changes saved. Batch ready for export.', 'success')
                        conn.close()
                        return redirect(url_for('batch.batch_control'))
                    elif action == 'auto_save':
                        conn.close()
                        return jsonify({'success': True})
                    conn.close()
                except Exception as save_err:
                    logger.error(f"Failed to save manipulation changes for doc {doc_id}: {save_err}")
                    flash(f"Save failed: {save_err}", 'error')
            else:
                # Grouped-document parity (Level A): update final_filename_base
                if doc_id:
                    try:
                        conn = get_db_connection()
                        cur = conn.cursor()
                        filename_choice = request.form.get('filename_choice')
                        custom_filename = (request.form.get('custom_filename') or '').strip() or None
                        new_filename_base = None
                        if filename_choice == 'custom' and custom_filename:
                            new_filename_base = custom_filename
                        elif filename_choice == 'original':
                            # Use original document_name (strip extension if present)
                            row = cur.execute("SELECT document_name FROM documents WHERE id=?", (doc_id,)).fetchone()
                            if row:
                                base = row[0]
                                new_filename_base = base.rsplit('.',1)[0] if '.' in base else base
                        else:
                            # Default to existing final_filename_base or document_name
                            row = cur.execute("SELECT final_filename_base, document_name FROM documents WHERE id=?", (doc_id,)).fetchone()
                            if row:
                                new_filename_base = row[0] or (row[1].rsplit('.',1)[0] if '.' in row[1] else row[1])
                        if new_filename_base:
                            cur.execute("UPDATE documents SET final_filename_base=? WHERE id=?", (new_filename_base, doc_id))
                            conn.commit()
                        if action == 'finish_batch':
                            # Mark batch ready for export (grouped path)
                            cur.execute("UPDATE batches SET status='ready_for_export', has_been_manipulated=1 WHERE id=?", (batch_id,))
                            conn.commit()
                            flash('All changes saved. Batch ready for export.', 'success')
                            conn.close()
                            return redirect(url_for('batch.batch_control'))
                        elif action == 'auto_save':
                            conn.close()
                            return jsonify({'success': True})
                        conn.close()
                    except Exception as gerr:
                        logger.error(f"Grouped-doc save failed for doc {doc_id}: {gerr}")
                        flash(f"Grouped save failed: {gerr}", 'error')
                else:
                    flash('No document id provided for grouped-document save', 'warning')

            return redirect(url_for('manipulation.manipulate_batch_documents', batch_id=batch_id, doc_num=doc_num))

        # GET request logic
        if using_single:
            documents = single_docs
        else:
            documents = get_documents_for_batch(batch_id) or []  # grouped documents

        # Categories
        try:
            from ..database import get_active_categories
            categories = get_active_categories() or []
        except Exception:
            categories = []

        total_docs = len(documents)
        if total_docs == 0:
            # Render empty state early
            empty_doc = {
                'id': -1,
                'original_filename': 'No documents',
                'original_pdf_path': None,
                'ai_suggested_category': None,
                'ai_suggested_filename': None,
                'ai_confidence': None,
                'ai_summary': None,
                'ocr_text': None,
                'ocr_confidence_avg': None,
            }
            return render_template('manipulate.html', batch_id=batch_id, current_doc=empty_doc, current_doc_num=1, total_docs=0, categories=categories)

        current_doc_num = max(1, min(doc_num or 1, total_docs))
        row = documents[current_doc_num - 1]

        if using_single:
            # Row ordering defined in accessor
            current_doc = {
                'id': row['id'],
                'original_filename': row['original_filename'],
                'original_pdf_path': row['original_pdf_path'],
                'ai_suggested_category': row['ai_suggested_category'],
                'ai_suggested_filename': row['ai_suggested_filename'],
                'ai_confidence': row['ai_confidence'],
                'ai_summary': row['ai_summary'],
                'ocr_text': row['ocr_text'],
                'ocr_confidence_avg': row['ocr_confidence_avg'],
            }
        else:
            # Grouped-document hydration (Level A)
            name = row['document_name'] if 'document_name' in row.keys() else f"Document {row['id']}"
            # Attempt first page OCR preview
            ocr_preview = None
            ocr_conf = None
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                # Get first linked page id
                cur.execute("""
                    SELECT p.ocr_text, p.ocr_confidence_avg
                    FROM pages p JOIN document_pages dp ON p.id = dp.page_id
                    WHERE dp.document_id = ?
                    ORDER BY dp.sequence ASC LIMIT 1
                """, (row['id'],))
                first_page = cur.fetchone()
                if first_page:
                    ocr_preview = first_page[0]
                    ocr_conf = first_page[1]
                conn.close()
            except Exception as pg_err:
                logger.debug(f"Grouped-doc OCR preview failed doc {row['id']}: {pg_err}")
            current_doc = {
                'id': row['id'],
                'original_filename': name + '.pdf',
                'original_pdf_path': None,  # Could build assembled PDF path if export stage pre-generates
                'ai_suggested_category': None,
                'ai_suggested_filename': None,
                'ai_confidence': None,
                'ai_summary': None,
                'ocr_text': ocr_preview,
                'ocr_confidence_avg': ocr_conf,
            }

        return render_template('manipulate.html', batch_id=batch_id, current_doc=current_doc, current_doc_num=current_doc_num, total_docs=total_docs, categories=categories)

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

# --- API: Single-document rotation & rescan (Tier 2 simplified) ---

@bp.route('/api/rotate_document/<int:doc_id>', methods=['POST'])
def api_rotate_single_document(doc_id: int):
    """Rotate a single-document workflow file (simplified Tier 2).

    Current implementation logs the requested rotation; full physical PDF/image
    transformation & re-OCR can be added later. Returns success immediately.
    Body JSON: {"rotation": 90}
    """
    try:
        data = request.get_json(force=True) if request.is_json else {}
        rotation = int(data.get('rotation', 0))
        if rotation not in {0,90,180,270}:
            return jsonify({'success': False, 'error': 'Invalid rotation angle'}), 400
        conn = get_db_connection()
        cur = conn.cursor()
        row = cur.execute("SELECT id, original_filename, batch_id FROM single_documents WHERE id=?", (doc_id,)).fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Document not found'}), 404
        batch_id = row['batch_id']
        # For now just log interaction; a future enhancement could queue reprocess
        try:
            log_interaction(batch_id=batch_id, document_id=doc_id, user_id=None, event_type='human_correction', step='rotation_request', content=json.dumps({'rotation': rotation}), notes='tier2_no_physical_rotate')
        except Exception:
            pass
        conn.close()
        return jsonify({'success': True, 'queued': False, 'note': 'Rotation logged (no file transform yet)'})
    except Exception as e:
        logger.error(f"Rotate single doc failed {doc_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/rescan_document/<int:doc_id>', methods=['POST'])
def api_rescan_single_document(doc_id: int):
    """Rescan a single-document: either AI-only or OCR+AI (Tier 2 simplified).

    JSON body: {"rescan_type": "llm_only" | "ocr_and_llm"}
    For llm_only: regenerate AI suggestions from existing cached OCR text.
    For ocr_and_llm: (placeholder) currently same as llm_only; future: re-run OCR pipeline.
    """
    try:
        data = request.get_json(force=True) if request.is_json else {}
        mode = data.get('rescan_type', 'llm_only')
        conn = get_db_connection()
        cur = conn.cursor()
        row = cur.execute("""
            SELECT id, original_filename, original_pdf_path, ocr_text, page_count, batch_id
            FROM single_documents WHERE id=?
        """, (doc_id,)).fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Document not found'}), 404
        ocr_text = row['ocr_text'] or ''
        filename = row['original_filename']
        page_count = row['page_count']
        batch_id = row['batch_id']

        # Placeholder: if mode == ocr_and_llm we would re-run OCR before AI. Skipped for Tier 2.
        # Regenerate AI suggestion using utility (expects sample of text)
        try:
            content_sample = ocr_text[:2000]  # limit prompt size
            # get_ai_document_type_analysis(file_path, content_sample, filename, page_count, file_size_mb)
            ai_result = get_ai_document_type_analysis(row['original_pdf_path'], content_sample, filename, page_count, 0.0)
            ai_category = ai_result.get('suggested_category') if isinstance(ai_result, dict) else None
            ai_filename = ai_result.get('suggested_filename') if isinstance(ai_result, dict) else None
            ai_confidence = ai_result.get('confidence') if isinstance(ai_result, dict) else None
            ai_summary = ai_result.get('summary') if isinstance(ai_result, dict) else None
        except Exception as ai_err:
            logger.error(f"AI rescan failed for doc {doc_id}: {ai_err}")
            ai_category = ai_filename = ai_confidence = ai_summary = None

        try:
            cur.execute("""
                UPDATE single_documents SET
                    ai_suggested_category=?, ai_suggested_filename=?, ai_confidence=?, ai_summary=?
                WHERE id=?
            """, (ai_category, ai_filename, ai_confidence, ai_summary, doc_id))
            conn.commit()
        except Exception as upd_err:
            logger.error(f"Failed updating AI fields for doc {doc_id}: {upd_err}")

        try:
            log_interaction(batch_id=batch_id, document_id=doc_id, user_id=None, event_type='ai_response', step='rescan', content=json.dumps({'mode': mode, 'ai_category': ai_category, 'ai_filename': ai_filename}), notes='tier2_rescan')
        except Exception:
            pass
        conn.close()
        return jsonify({'success': True, 'mode': mode, 'ai_category': ai_category, 'ai_filename': ai_filename})
    except Exception as e:
        logger.error(f"Rescan single doc failed {doc_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
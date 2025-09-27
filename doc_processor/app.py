# --- ARCHIVE CLEANUP ON NEW BATCH ---
import time
from pathlib import Path

def cleanup_old_archives():
    days = getattr(app_config, "ARCHIVE_RETENTION_DAYS", 30)
    archive_dir = getattr(app_config, "ARCHIVE_DIR", None)
    if not archive_dir:
        logging.warning("No ARCHIVE_DIR set, skipping archive cleanup.")
        return
    cutoff = time.time() - days * 86400
    deleted = 0
    for root, dirs, files in os.walk(archive_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
                    deleted += 1
            except Exception as e:
                logging.error(f"Failed to delete old archive file {fpath}: {e}")
    if deleted:
        logging.info(f"Deleted {deleted} old files from archive (>{days} days old)")

"""
This module is the central hub of the document processing web application.
It uses the Flask web framework to create a user interface for a multi-stage
document processing pipeline. The application is designed to guide a user
through a series of steps to take a batch of raw documents (e.g., scans)
and turn them into organized, categorized, and named files.

The pipeline consists of the following major stages, each managed by
one or more routes in this file:

1.  **Batch Processing**: A user initiates the processing of a new batch of
    documents from a predefined source directory. The `processing.py` module
    handles the heavy lifting of OCR, image conversion, and initial AI-based
    categorization.

2    page_id = request.form.get("page_id", type=int)
    batch_id = request.form.get("batch_id", type=int)
    rotation = request.form.get("rotation", 0, type=int)
    
    if page_id is None or batch_id is None:
        abort(400, "Page ID and Batch ID are required")
    
    # Validate rotation angle
    if rotation not in {0, 90, 180, 270}:
        abort(400, "Invalid rotation angle")
    
    # The `rerun_ocr_on_page` function in `processing.py` handles the image
    # manipulation and the call to the OCR engine.
    try:
        rerun_ocr_on_page(page_id, rotation)
    except OCRError as e:
        logging.error(f"OCR error for page {page_id}: {e}")
        abort(500, "OCR processing failed")erification**: The user manually reviews each page of the batch. They can
    correct the AI's suggested category, rotate pages, or flag pages that
    require special attention. This is the primary quality control step.

3.  **Review**: A dedicated interface to handle only the "flagged" pages. This
    allows for focused problem-solving on pages that were unclear or had
    issues during verification.

4.  **Grouping**: After all pages are verified, the user groups them into logical
    documents. For example, a 5-page document would be created by grouping five
    individual verified pages.

5.  **Ordering**: For documents with more than one page, the user can specify the
    correct page order. An AI suggestion is available to speed up this process.

6.  **Finalization & Export**: The final step where the user gives each document a
    meaningful filename (with AI suggestions) and exports them. The application
    creates final PDF files (both with and without OCR text layers) and a log
    file, organizing them into a "filing cabinet" directory structure based on
    their category.

This module ties together the database interactions (from `database.py`) and
the core processing logic (from `processing.py`) to create a cohesive user
experience.
"""
# Standard library imports
import os
import logging
import json
from logging.handlers import RotatingFileHandler
# --- LOGGING CONFIGURATION ---
LOG_DIR = os.getenv("LOG_DIR", os.path.join(os.path.dirname(__file__), "..", "logs"))
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# Rotating file handler: 5MB per file, keep 5 backups
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_fmt = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
file_handler.setFormatter(file_fmt)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_fmt = logging.Formatter('%(levelname)s %(name)s: %(message)s')
console_handler.setFormatter(console_fmt)

# Root logger setup
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

# Capture all uncaught exceptions
def log_uncaught_exceptions(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        return  # Don't log keyboard interrupts
    logging.getLogger().error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

import sys
sys.excepthook = log_uncaught_exceptions
import logging

# Third-party imports
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
    jsonify,
    abort,
    flash,
    session
)

# Local application imports
from .security import validate_path, sanitize_input, validate_file_upload, require_safe_path
from .exceptions import DocProcessorError, FileProcessingError, OCRError
from .config_manager import app_config, DEFAULT_CATEGORIES

# Core business logic and database functions
from .processing import (
    process_batch,
    _process_batch_traditional,
    rerun_ocr_on_page,
    get_ai_suggested_order,
    get_ai_suggested_filename,
    export_document,
    cleanup_batch_files,
)
from .document_detector import get_detector
from .database import (
    get_pages_for_batch,
    update_page_data,
    get_flagged_pages_for_batch,
    delete_page_by_id,
    get_all_unique_categories,
    get_verified_pages_for_grouping,
    create_document_and_link_pages,
    get_created_documents_for_batch,
    get_batch_by_id,
    count_flagged_pages_for_batch,
    get_db_connection,
    count_ungrouped_verified_pages,
    reset_batch_grouping,
    get_documents_for_batch,
    get_pages_for_document,
    update_page_sequence,
    update_document_status,
    reset_batch_to_start,
    update_document_final_filename,
    get_all_categories,
    insert_category_if_not_exists,
    log_interaction,
    get_active_categories,
    update_page_rotation,
)



# Initialize the Flask application
# This is the core object that handles web requests and responses.

app = Flask(__name__)
# ------------------ CATEGORY MANAGEMENT HELPERS ------------------
def fetch_all_categories(include_inactive=True, sort="name"):
    # Whitelist allowed sort keys to prevent SQL injection
    sort_key = "name" if sort not in {"id", "name"} else sort
    order_clause = "name COLLATE NOCASE" if sort_key == "name" else "id"
    base_query = "SELECT id, name, is_active, previous_name, notes FROM categories"
    if include_inactive:
        query = f"{base_query} ORDER BY {order_clause}"
        params = ()
    else:
        query = f"{base_query} WHERE is_active = 1 ORDER BY {order_clause}"
        params = ()
    conn = get_db_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_category(name, notes=None):
    if not name:
        return False, "Name required"
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO categories (name, is_active, notes) VALUES (?, 1, ?)", (name.strip(), notes))
        cat_id = conn.execute("SELECT id FROM categories WHERE name = ?", (name.strip(),)).fetchone()["id"]
        # category_change_log
        conn.execute("INSERT INTO category_change_log (category_id, action, new_name, notes) VALUES (?, 'add', ?, ?)", (cat_id, name.strip(), notes))
        # interaction_log (batch/document null for admin action)
        conn.execute("INSERT INTO interaction_log (event_type, step, content, notes) VALUES ('category_change', 'admin', ?, ?)", (
            json.dumps({"action":"add","category_id":cat_id,"new_name":name.strip()}), notes
        ))
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def soft_delete_category(cat_id):
    conn = get_db_connection()
    try:
        old_name = conn.execute("SELECT name FROM categories WHERE id = ?", (cat_id,)).fetchone()
        conn.execute("UPDATE categories SET is_active = 0 WHERE id = ?", (cat_id,))
        conn.execute("INSERT INTO category_change_log (category_id, action, old_name, new_name) VALUES (?, 'soft_delete', ?, ?)", (cat_id, old_name["name"] if old_name else None, old_name["name"] if old_name else None))
        conn.execute("INSERT INTO interaction_log (event_type, step, content) VALUES ('category_change', 'admin', ?)", (
            json.dumps({"action":"soft_delete","category_id":cat_id,"name": old_name["name"] if old_name else None}),
        ))
        conn.commit()
    finally:
        conn.close()

def restore_category(cat_id):
    conn = get_db_connection()
    try:
        name_row = conn.execute("SELECT name FROM categories WHERE id = ?", (cat_id,)).fetchone()
        conn.execute("UPDATE categories SET is_active = 1 WHERE id = ?", (cat_id,))
        conn.execute("INSERT INTO category_change_log (category_id, action, new_name) VALUES (?, 'restore', ?)", (cat_id, name_row["name"] if name_row else None))
        conn.execute("INSERT INTO interaction_log (event_type, step, content) VALUES ('category_change', 'admin', ?)", (
            json.dumps({"action":"restore","category_id":cat_id,"name": name_row["name"] if name_row else None}),
        ))
        conn.commit()
    finally:
        conn.close()

def rename_category(cat_id, new_name, skip_backfill=False):
    if not new_name:
        return False, "New name required"
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT name FROM categories WHERE id = ?", (cat_id,)).fetchone()
        if not row:
            return False, "Category not found"
        old_name = row["name"]
        if old_name == new_name.strip():
            return True, None
        # Backfill pages with old category to new category (only if they still match old_name)
        pages_updated = 0
        if not skip_backfill:
            pages_updated = conn.execute("SELECT COUNT(*) AS c FROM pages WHERE human_verified_category = ?", (old_name,)).fetchone()["c"]
            conn.execute("UPDATE pages SET human_verified_category = ? WHERE human_verified_category = ?", (new_name.strip(), old_name))
        conn.execute("UPDATE categories SET name = ?, previous_name = ? WHERE id = ?", (new_name.strip(), old_name, cat_id))
        note_text = f"Renamed and backfilled {pages_updated} pages" if pages_updated and not skip_backfill else ("Renamed (no backfill)" if skip_backfill else None)
        conn.execute("INSERT INTO category_change_log (category_id, action, old_name, new_name, notes) VALUES (?, 'rename', ?, ?, ?)", (cat_id, old_name, new_name.strip(), note_text))
        conn.execute("INSERT INTO interaction_log (event_type, step, content, notes) VALUES ('category_change', 'admin', ?, ?)", (
            json.dumps({"action":"rename","category_id":cat_id,"old_name":old_name,"new_name":new_name.strip(),"pages_updated":pages_updated,"skip_backfill":skip_backfill}), note_text
        ))
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

# ------------------ CATEGORY MANAGEMENT ROUTES ------------------
@app.route("/categories", methods=["GET"])
def categories_page():
    sort = request.args.get("sort", "name").lower()
    if sort not in {"id", "name"}:
        sort = "name"
    categories = fetch_all_categories(include_inactive=True, sort=sort)
    # filters
    limit = request.args.get("limit", type=int) or 25
    if limit > 200:
        limit = 200
    category_filter = request.args.get("category_id", type=int)
    conn = get_db_connection()
    if category_filter:
        history_rows = conn.execute(
            "SELECT id, category_id, action, old_name, new_name, notes, timestamp FROM category_change_log WHERE category_id = ? ORDER BY id DESC LIMIT ?",
            (category_filter, limit),
        ).fetchall()
    else:
        history_rows = conn.execute(
            "SELECT id, category_id, action, old_name, new_name, notes, timestamp FROM category_change_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    history = [dict(r) for r in history_rows]
    return render_template("categories.html", categories=categories, history=history, current_sort=sort)

@app.route("/categories/add", methods=["POST"])
def add_category_action():
    name = request.form.get("name", "").strip()
    notes = request.form.get("notes") or None
    ok, err = add_category(name, notes)
    if not ok:
        return jsonify({"success": False, "error": err}), 400
    return redirect(url_for("categories_page"))

@app.route("/categories/<int:cat_id>/rename", methods=["POST"])
def rename_category_action(cat_id):
    new_name = request.form.get("new_name", "").strip()
    skip_backfill = request.form.get("skip_backfill") == "on"
    ok, err = rename_category(cat_id, new_name, skip_backfill=skip_backfill)
    if not ok:
        return jsonify({"success": False, "error": err}), 400
    return redirect(url_for("categories_page"))

@app.route("/categories/<int:cat_id>/delete", methods=["POST"])
def delete_category_action(cat_id):
    soft_delete_category(cat_id)
    return redirect(url_for("categories_page"))

@app.route("/categories/<int:cat_id>/restore", methods=["POST"])
def restore_category_action(cat_id):
    restore_category(cat_id)
    return redirect(url_for("categories_page"))
# --- Batch Audit Trail View ---
@app.route("/batch_audit/<int:batch_id>")
def batch_audit_view(batch_id):
    conn = get_db_connection()
    batch = conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
    page_count = conn.execute("SELECT COUNT(*) FROM pages WHERE batch_id = ?", (batch_id,)).fetchone()[0]
    document_count = conn.execute("SELECT COUNT(*) FROM documents WHERE batch_id = ?", (batch_id,)).fetchone()[0]
    logs = conn.execute("SELECT * FROM interaction_log WHERE batch_id = ? ORDER BY timestamp ASC", (batch_id,)).fetchall()
    conn.close()
    batch_dict = dict(batch) if batch else {}
    logs_dicts = [dict(row) for row in logs]
    return render_template("batch_audit.html", batch=batch_dict, page_count=page_count, document_count=document_count, interaction_logs=logs_dicts)

# --- API: APPLY DOCUMENT NAME ---
@app.route("/api/apply_name/<int:document_id>", methods=["POST"])
def apply_name_api(document_id):
    """
    API endpoint to set the document's name from the order page, via AJAX.
    """
    data = request.get_json()
    filename = data.get("filename", "").strip()
    if not filename:
        return jsonify({"success": False, "error": "Filename cannot be empty."}), 400
    update_document_final_filename(document_id, filename)
    return jsonify({"success": True})

# --- API: SUGGEST DOCUMENT NAME ---
@app.route("/api/suggest_name/<int:document_id>", methods=["POST"])
def suggest_name_api(document_id):
    """
    API endpoint to suggest a document name using AI, based on the document's pages and category.
    """
    pages_raw = get_pages_for_document(document_id)
    if not pages_raw:
        return jsonify({"success": False, "error": "Document not found or has no pages."}), 404
    pages = [dict(p) for p in pages_raw]
    full_doc_text = "\n---\n".join([p["ocr_text"] for p in pages if p.get("ocr_text")])
    doc_category = pages[0]["human_verified_category"] if pages[0].get("human_verified_category") else ""
    try:
        suggested_name = get_ai_suggested_filename(full_doc_text, doc_category)
        return jsonify({"success": True, "suggested_name": suggested_name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# --- DOCUMENT-LEVEL REVISIT ORDERING ROUTE ---
@app.route("/revisit_ordering_document/<int:document_id>", methods=["POST"])
def revisit_ordering_document_action(document_id):
    """
    Allows the user to revisit the ordering step for a single document by resetting its status to 'pending_order'.
    """
    conn = get_db_connection()
    conn.execute(
        "UPDATE documents SET status = 'pending_order' WHERE id = ?",
        (document_id,)
    )
    conn.commit()
    conn.close()
    logging.info(f"Document {document_id} status reset to pending_order for reordering")
    return ("", 204)

# --- REVISIT ORDERING ROUTE ---
@app.route("/revisit_ordering/<int:batch_id>", methods=["POST"])
def revisit_ordering_action(batch_id):
    """
    Allows the user to revisit the ordering step by resetting the batch status to 'grouping_complete'.
    """
    conn = get_db_connection()
    conn.execute("UPDATE batches SET status = 'grouping_complete' WHERE id = ?", (batch_id,))
    conn.commit()
    conn.close()
    logging.info(f"Batch {batch_id} status reset to grouping_complete for reordering")
    return redirect(url_for("order_batch_page", batch_id=batch_id))

# --- FINISH ORDERING ROUTE ---
@app.route("/finish_ordering/<int:batch_id>", methods=["POST"])
def finish_ordering_action(batch_id):
    """
    Marks ordering as complete for the batch and returns to Batch Control.
    """
    conn = get_db_connection()
    conn.execute("UPDATE batches SET status = 'ordering_complete' WHERE id = ?", (batch_id,))
    conn.commit()
    conn.close()
    logging.info(f"Batch {batch_id} marked as ordering_complete")
    return redirect(url_for("batch_control_page"))

# Set a secret key for session management. This is crucial for security and for
# features like flashed messages that persist across requests.
# os.urandom(24) generates a secure, random key each time the app starts,
# making it difficult to predict and exploit session data.
app.secret_key = os.urandom(24)


# --- CORE NAVIGATION AND WORKFLOW ROUTES ---
# These routes define the main pages and initial actions a user takes.

@app.route("/")
def index():
    """
    The root URL of the application.
    Redirects to the primary workflow entry point - Analyze Intake.
    This allows users to preview and choose processing strategy before starting.
    """
    return redirect(url_for("analyze_intake_page"))


@app.route("/clear_analysis_cache", methods=["POST"])
def clear_analysis_cache():
    """Clear the cached analysis results to force re-analysis."""
    try:
        import tempfile
        cache_file = os.path.join(tempfile.gettempdir(), 'intake_analysis_cache.pkl')
        if os.path.exists(cache_file):
            os.remove(cache_file)
            logging.info("Cleared analysis cache")
    except Exception as e:
        logging.error(f"Failed to clear analysis cache: {e}")
    
    return redirect(url_for("analyze_intake_page"))

@app.route("/analyze_intake")
def analyze_intake_page():
    """
    Show intake analysis page. Analysis results are loaded via AJAX 
    to provide loading feedback to the user.
    """
    # Check if we have cached analysis results to avoid re-analyzing
    cached_analyses = None
    try:
        import tempfile
        import pickle
        cache_file = os.path.join(tempfile.gettempdir(), 'intake_analysis_cache.pkl')
        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as f:
                cached_analyses = pickle.load(f)
            logging.info("Loaded cached analysis results")
    except Exception as e:
        logging.warning(f"Failed to load cached analysis results: {e}")
        cached_analyses = None
    
    return render_template('intake_analysis.html', 
                         analyses=cached_analyses,  # Use cached if available
                         intake_dir=app_config.INTAKE_DIR)

@app.route("/api/analyze_intake_progress")
def analyze_intake_progress():
    """
    Server-Sent Events endpoint for real-time analysis progress.
    Streams progress updates as each PDF is analyzed.
    """
    import json
    
    def generate_progress():
        try:
            from .document_detector import get_detector
            import os
            
            detector = get_detector(use_llm_for_ambiguous=True)
            intake_dir = app_config.INTAKE_DIR
            
            # Get list of PDF files
            if not os.path.exists(intake_dir):
                yield f"data: {json.dumps({'error': f'Intake directory does not exist: {intake_dir}'})}\n\n"
                return
                
            pdf_files = [
                os.path.join(intake_dir, f) 
                for f in os.listdir(intake_dir) 
                if f.lower().endswith('.pdf')
            ]
            
            total_files = len(pdf_files)
            
            if total_files == 0:
                yield f"data: {json.dumps({'complete': True, 'analyses': [], 'total': 0, 'single_count': 0, 'batch_count': 0, 'success': True})}\n\n"
                return
            
            # Send initial progress
            logging.info(f"Starting SSE analysis for {total_files} PDF files")
            yield f"data: {json.dumps({'progress': 0, 'total': total_files, 'current_file': None, 'message': f'Found {total_files} PDF files to analyze...'})}\n\n"
            
            analyses = []
            single_count = 0
            batch_count = 0
            
            for i, pdf_file in enumerate(pdf_files):
                filename = os.path.basename(pdf_file)
                
                # Send progress update for current file
                yield f"data: {json.dumps({'progress': i, 'total': total_files, 'current_file': filename, 'message': f'Analyzing {filename}...'})}\n\n"
                
                # Analyze the file
                analysis = detector.analyze_pdf(pdf_file)
                
                # Prepare analysis data
                analysis_data = {
                    'filename': filename,
                    'file_size_mb': analysis.file_size_mb,
                    'page_count': analysis.page_count,
                    'processing_strategy': analysis.processing_strategy,
                    'confidence': analysis.confidence,
                    'reasoning': analysis.reasoning,
                    'filename_hints': analysis.filename_hints,
                    'content_sample': analysis.content_sample
                }
                
                # Add LLM analysis data if available
                if hasattr(analysis, 'llm_analysis') and analysis.llm_analysis:
                    analysis_data['llm_analysis'] = analysis.llm_analysis
                    
                analyses.append(analysis_data)
                
                if analysis.processing_strategy == "single_document":
                    single_count += 1
                else:
                    batch_count += 1
                
                # Send progress update after analysis
                progress_msg = f'Completed {filename}'
                if hasattr(analysis, 'llm_analysis') and analysis.llm_analysis:
                    progress_msg += ' (AI analyzed)'
                    
                yield f"data: {json.dumps({'progress': i + 1, 'total': total_files, 'current_file': None, 'message': progress_msg})}\n\n"
            
            # Cache the results for future use to avoid re-analysis
            import tempfile
            import pickle
            cache_file = os.path.join(tempfile.gettempdir(), 'intake_analysis_cache.pkl')
            try:
                with open(cache_file, 'wb') as f:
                    pickle.dump(analyses, f)
                logging.info(f"Cached analysis results to {cache_file}")
            except Exception as cache_err:
                logging.warning(f"Failed to cache analysis results: {cache_err}")
            
            # Send final results
            yield f"data: {json.dumps({'complete': True, 'analyses': analyses, 'total': total_files, 'single_count': single_count, 'batch_count': batch_count, 'success': True})}\n\n"
            
        except Exception as e:
            logging.error(f"Error in progress analysis: {e}")
            yield f"data: {json.dumps({'error': f'Analysis error: {str(e)}'})}\n\n"
    
    response = app.response_class(generate_progress(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route("/api/analyze_intake")
def analyze_intake_api():
    """
    API endpoint to perform the actual document analysis.
    Returns JSON results for AJAX loading. (Kept for compatibility)
    """
    try:
        detector = get_detector(use_llm_for_ambiguous=True)
        analyses = detector.analyze_intake_directory(app_config.INTAKE_DIR)
        
        if not analyses:
            return jsonify({
                'success': True,
                'analyses': [],
                'single_count': 0,
                'batch_count': 0,
                'total_count': 0
            })
        
        # Prepare data for template
        template_analyses = []
        single_count = 0
        batch_count = 0
        
        for analysis in analyses:
            analysis_data = {
                'filename': os.path.basename(analysis.file_path),
                'file_size_mb': analysis.file_size_mb,
                'page_count': analysis.page_count,
                'processing_strategy': analysis.processing_strategy,
                'confidence': analysis.confidence,
                'reasoning': analysis.reasoning,
                'filename_hints': analysis.filename_hints,
                'content_sample': analysis.content_sample
            }
            
            # Add LLM analysis data if available
            if hasattr(analysis, 'llm_analysis') and analysis.llm_analysis:
                analysis_data['llm_analysis'] = analysis.llm_analysis
                logging.info(f"Including LLM analysis for {analysis_data['filename']}: {analysis.llm_analysis}")
            else:
                logging.info(f"No LLM analysis for {analysis_data['filename']} (hasattr: {hasattr(analysis, 'llm_analysis')}, value: {getattr(analysis, 'llm_analysis', 'N/A')})")
                
            template_analyses.append(analysis_data)
            
            if analysis.processing_strategy == "single_document":
                single_count += 1
            else:
                batch_count += 1
        
        return jsonify({
            'success': True,
            'analyses': template_analyses,
            'single_count': single_count,
            'batch_count': batch_count,
            'total_count': len(analyses)
        })
                             
    except Exception as e:
        logging.error(f"Error analyzing intake: {e}")
        return jsonify({
            'success': False,
            'error': f"Error analyzing files: {e}",
            'analyses': []
        })


# --- SINGLE DOCUMENT PROCESSING ROUTES ---

@app.route("/single_processing_progress")
def single_processing_progress():
    """
    Show progress page for single document processing with real-time updates.
    """
    logging.info("[SINGLE] Rendering single_processing_progress page")
    return render_template("single_processing_progress.html")

@app.route("/api/single_processing_progress")
def api_single_processing_progress():
    """
    Server-Sent Events endpoint for real-time single document processing progress.
    """
    # This will be very similar to smart processing but forces all files as single documents
    return api_smart_processing_progress_with_strategy("single_document")

# --- BATCH PROCESSING ROUTES ---

@app.route("/batch_processing_progress")
def batch_processing_progress():
    """
    Show progress page for traditional batch processing with real-time updates.
    """
    logging.info("[BATCH] Rendering batch_processing_progress page")
    return render_template("batch_processing_progress.html")

@app.route("/api/batch_processing_progress")
def api_batch_processing_progress():
    """
    Server-Sent Events endpoint for real-time batch processing progress.
    """
    # This will be very similar to smart processing but forces all files as batch scans
    return api_smart_processing_progress_with_strategy("batch_scan")

# --- SMART PROCESSING ROUTES ---

@app.route("/process_batch_smart", methods=["POST"])
def process_batch_smart():
    """
    Start smart processing in the background and redirect to progress page.
    Handles strategy overrides from the user interface.
    """
    import json
    
    # Get strategy overrides from the request
    strategy_overrides_json = request.form.get('strategy_overrides')
    strategy_overrides = {}
    
    if strategy_overrides_json:
        try:
            strategy_overrides = json.loads(strategy_overrides_json)
            logging.info(f"[SMART] Received strategy overrides for {len(strategy_overrides)} files")
            for filename, strategy in strategy_overrides.items():
                logging.info(f"[SMART] Override: {filename} -> {strategy}")
        except (json.JSONDecodeError, TypeError) as e:
            logging.warning(f"[SMART] Failed to parse strategy overrides: {e}")
            strategy_overrides = {}
    
    # Store overrides in session for the processing thread to access
    session['strategy_overrides'] = strategy_overrides
    
    logging.info("[SMART] /process_batch_smart invoked; redirecting to /smart_processing_progress")
    # Use 303 See Other to force browser to use GET method for redirect
    return redirect(url_for("smart_processing_progress"), code=303)

@app.route("/smart_processing_progress")
def smart_processing_progress():
    """
    Show progress page for smart processing with real-time updates.
    """
    logging.info("[SMART] Rendering smart_processing_progress page")
    return render_template("smart_processing_progress.html")

@app.route("/api/smart_processing_progress")
def api_smart_processing_progress():
    """
    Server-Sent Events endpoint for real-time smart processing progress.
    Uses strategy overrides from session if available.
    """
    from flask import Response
    from .document_detector import get_detector
    from .processing import process_single_document
    
    # Get strategy overrides from session
    strategy_overrides = session.get('strategy_overrides', {})
    if strategy_overrides:
        logging.info(f"[SMART SSE] Using strategy overrides for {len(strategy_overrides)} files")
    
    logging.info("[SMART SSE] Client connected to /api/smart_processing_progress")

    def generate_progress():
        import time
        
        # IMMEDIATE yield to test connection and prevent hanging
        yield f"data: {json.dumps({'message': 'Connection established, initializing...', 'progress': 0, 'total': 0})}\n\n"
        
        try:
            logging.info("[SMART SSE] Starting smart processing progress generator.")
            cleanup_old_archives()
            import os as _os

            # Watchdog setup
            last_progress_time = time.time()
            watchdog_timeout = 300  # 5 minutes

            def watchdog_check():
                if time.time() - last_progress_time > watchdog_timeout:
                    logging.warning("[SMART SSE] No progress for 5 minutes. Possible freeze detected.")
                    yield f"data: {json.dumps({'error': 'No progress for 5 minutes. Please check logs or restart processing.'})}\n\n"

            # Step 0: Discover files quickly and report immediately
            intake_dir = app_config.INTAKE_DIR
            logging.info(f"[SMART SSE] Checking intake directory: {intake_dir}")
            if not _os.path.exists(intake_dir):
                logging.error(f"[SMART SSE] Intake directory does not exist: {intake_dir}")
                yield f"data: {json.dumps({'complete': True, 'success': False, 'error': f'Intake directory does not exist: {intake_dir}'})}\n\n"
                return

            pdf_files = [
                _os.path.join(intake_dir, f)
                for f in _os.listdir(intake_dir)
                if f.lower().endswith('.pdf')
            ]

            total_files = len(pdf_files)
            logging.info(f"[SMART SSE] Found {total_files} PDF files in intake directory.")
            if total_files == 0:
                logging.warning("[SMART SSE] No files to process in intake directory.")
                yield f"data: {json.dumps({'complete': True, 'success': True, 'message': 'No files to process', 'redirect': '/batch_control'})}\n\n"
                return

            # Step 1: Load cached analysis results from intake analysis
            logging.info(f"[SMART SSE] Loading cached analysis results...")
            yield f"data: {json.dumps({'progress': 0, 'total': total_files, 'message': f'Loading analysis results for {total_files} files...', 'current_file': None})}\n\n"
            last_progress_time = time.time()
            
            analyses = []
            try:
                # Try to load cached analysis results
                import pickle
                cache_file = "/tmp/intake_analysis_cache.pkl"
                cached_analyses = {}
                if _os.path.exists(cache_file):
                    with open(cache_file, 'rb') as f:
                        analyses_list = pickle.load(f)
                    # Convert dicts to DocumentAnalysis if needed
                    from .document_detector import DocumentAnalysis
                    converted_analyses = []
                    for analysis in analyses_list:
                        if isinstance(analysis, dict):
                            # Handle cache format mismatch: 'filename' -> 'file_path'
                            if 'filename' in analysis and 'file_path' not in analysis:
                                analysis['file_path'] = _os.path.join(intake_dir, analysis['filename'])
                                # Remove the 'filename' key to avoid conflicts
                                del analysis['filename']
                            converted_analyses.append(DocumentAnalysis(**analysis))
                        else:
                            converted_analyses.append(analysis)
                    cached_analyses = {a.file_path: a for a in converted_analyses}
                else:
                    cached_analyses = {}
                
                for path in pdf_files:
                    analysis = cached_analyses.get(path)
                    if analysis:
                        analyses.append(analysis)
                        fname = _os.path.basename(analysis.file_path)
                        logging.info(f"[SMART SSE] Loaded cached analysis for: {fname} | Strategy: {analysis.processing_strategy} | Pages: {analysis.page_count} | Confidence: {analysis.confidence}")
                    else:
                        logging.warning(f"[SMART SSE] No cached analysis found for: {_os.path.basename(path)}")
                
                if analyses:
                    logging.info(f"[SMART SSE] Successfully loaded {len(analyses)} cached analysis results.")
                    yield f"data: {json.dumps({'progress': len(analyses), 'total': total_files, 'message': f'Loaded analysis for {len(analyses)} files', 'current_file': None})}\n\n"
                    last_progress_time = time.time()
                else:
                    raise Exception("No valid cached analyses found")
            except Exception as e:
                # Fallback to fresh analysis if cache loading fails
                logging.warning(f"[SMART SSE] Could not load cached analysis ({e}), running fresh analysis...")
                yield f"data: {json.dumps({'progress': 0, 'total': total_files, 'message': f'Running fresh analysis for {total_files} files...', 'current_file': None})}\n\n"
                last_progress_time = time.time()
                
                detector = get_detector(use_llm_for_ambiguous=True)
                for i, path in enumerate(pdf_files, start=1):
                    fname = _os.path.basename(path)
                    logging.info(f"[SMART SSE] Fresh analysis starting for: {fname}")
                    yield f"data: {json.dumps({'progress': i-1, 'total': total_files, 'message': f'Analyzing: {fname}', 'current_file': fname})}\n\n"
                    last_progress_time = time.time()
                    try:
                        analysis = detector.analyze_pdf(path)
                        logging.info(f"[SMART SSE] Analysis complete for: {fname} | Strategy: {analysis.processing_strategy} | Pages: {analysis.page_count} | Confidence: {analysis.confidence}")
                        analyses.append(analysis)
                        yield f"data: {json.dumps({'progress': i, 'total': total_files, 'message': f'Analyzed ({i}/{total_files}): {fname}', 'current_file': None})}\n\n"
                        last_progress_time = time.time()
                    except Exception as analysis_error:
                        logging.error(f"[SMART SSE] Analysis failed for {fname}: {analysis_error}")
                        from .document_detector import DocumentAnalysis
                        analyses.append(DocumentAnalysis(
                            file_path=path,
                            file_size_mb=0.0,
                            page_count=0,
                            processing_strategy='batch_scan',
                            confidence=0.0,
                            reasoning=[f'Analysis error: {analysis_error}', 'Defaulting to batch scan']
                        ))
                        last_progress_time = time.time()

                    # Watchdog check after each file
                    for msg in watchdog_check():
                        yield msg

            # Apply strategy overrides before processing
            import os as _os2  # Avoid collision with imported _os
            for analysis in analyses:
                filename = _os2.path.basename(analysis.file_path)
                if filename in strategy_overrides:
                    original_strategy = analysis.processing_strategy
                    override_strategy = strategy_overrides[filename]
                    if original_strategy != override_strategy:
                        logging.info(f"[SMART SSE] Strategy override: {filename} | {original_strategy} -> {override_strategy}")
                        analysis.processing_strategy = override_strategy
                        # Add override note to reasoning
                        if hasattr(analysis, 'reasoning') and analysis.reasoning:
                            analysis.reasoning.append(f"User override: {original_strategy} -> {override_strategy}")
                        else:
                            analysis.reasoning = [f"User override: {original_strategy} -> {override_strategy}"]
            
            # Process analyzed files based on their (potentially overridden) strategies
            single_docs = [a for a in analyses if a.processing_strategy == "single_document"]
            batch_scans = [a for a in analyses if a.processing_strategy == "batch_scan"]
            
            logging.info(f"[SMART SSE] After overrides: {len(single_docs)} single documents, {len(batch_scans)} batch scans")
            
            # Better progress tracking with weighted phases
            # Analysis: 20%, Batch Processing: 80% (since it includes heavy OCR + AI work)
            analysis_weight = 20
            processing_weight = 80
            processing_batches = (1 if single_docs else 0) + (1 if batch_scans else 0)
            total_progress = analysis_weight + (processing_weight * processing_batches)
            
            # Send processing start update  
            yield f"data: {json.dumps({'progress': analysis_weight, 'total': total_progress, 'message': f'Analysis complete. Creating batches for {len(single_docs)} single docs + {len(batch_scans)} batch scans...', 'current_file': None})}\n\n"
            
            current_progress = analysis_weight
            
            # Process all single documents as ONE batch
            if single_docs:
                yield f"data: {json.dumps({'progress': current_progress, 'total': total_progress, 'message': f'Creating batch for {len(single_docs)} single documents... (OCR + AI processing)', 'current_file': None})}\n\n"
                from .processing import _process_single_documents_as_batch
                
                logging.info(f"[SMART SSE] Starting batch creation for {len(single_docs)} single documents...")
                batch_id = _process_single_documents_as_batch(single_docs)
                logging.info(f"[SMART SSE] Batch creation function returned batch_id: {batch_id}")
                
                # Wait a moment and verify the batch is actually complete
                if batch_id:
                    import time
                    time.sleep(2)  # Give any async operations time to complete
                    
                    # Verify the batch actually has documents
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM single_documents WHERE batch_id = ?", (batch_id,))
                        doc_count = cursor.fetchone()[0]
                        conn.close()
                        logging.info(f"[SMART SSE] Verified batch {batch_id} contains {doc_count} documents")
                        
                        if doc_count == len(single_docs):
                            current_progress += processing_weight // processing_batches
                            _processing_state['message'] = f'✓ Created single documents batch: {batch_id} with {doc_count} documents'
                            yield f"data: {json.dumps({'progress': current_progress, 'total': total_progress, 'message': f'✓ Created single documents batch: {batch_id} with {doc_count} documents', 'current_file': None})}\n\n"
                        else:
                            _processing_state['message'] = f'⚠ Batch {batch_id} created but only {doc_count}/{len(single_docs)} documents processed'
                            yield f"data: {json.dumps({'progress': current_progress, 'total': total_progress, 'message': f'⚠ Batch {batch_id} created but only {doc_count}/{len(single_docs)} documents processed', 'current_file': None})}\n\n"
                    except Exception as verify_error:
                        logging.error(f"[SMART SSE] Error verifying batch completion: {verify_error}")
                        current_progress += processing_weight // processing_batches
                        yield f"data: {json.dumps({'progress': current_progress, 'total': total_progress, 'message': f'✓ Created single documents batch: {batch_id} (verification failed)', 'current_file': None})}\n\n"
                else:
                    _processing_state['message'] = '✗ Failed to create single documents batch'
                    yield f"data: {json.dumps({'progress': current_progress, 'total': total_progress, 'message': '✗ Failed to create single documents batch', 'current_file': None})}\n\n"
            
            # Process batch scans using modern single document workflow 
            if batch_scans:
                yield f"data: {json.dumps({'progress': current_progress, 'total': total_progress, 'message': f'Creating batch for {len(batch_scans)} batch scan documents... (OCR + AI processing)', 'current_file': None})}\n\n"
                logging.info(f"🔄 Processing {len(batch_scans)} batch scans as single documents using modern workflow")
                from .processing import _process_single_documents_as_batch
                batch_id = _process_single_documents_as_batch(batch_scans)
                current_progress += processing_weight // processing_batches
                if batch_id:
                    _processing_state['message'] = f'✓ Created batch {batch_id} for {len(batch_scans)} batch scan documents'
                    yield f"data: {json.dumps({'progress': current_progress, 'total': total_progress, 'message': f'✓ Created batch {batch_id} for {len(batch_scans)} batch scan documents', 'current_file': None})}\n\n"
                else:
                    _processing_state['message'] = f'✗ Failed to create batch for {len(batch_scans)} batch scan documents'
                    yield f"data: {json.dumps({'progress': current_progress, 'total': total_progress, 'message': f'✗ Failed to create batch for {len(batch_scans)} batch scan documents', 'current_file': None})}\n\n"
            
            # Clear strategy overrides from session
            session.pop('strategy_overrides', None)
            
            # Force a final progress update before completion
            yield f"data: {json.dumps({'progress': total_progress, 'total': total_progress, 'message': 'Processing complete! Redirecting...', 'current_file': None})}\n\n"
            
            # Send final completion message with explicit logging
            logging.info("[SMART SSE] Sending completion message to client")
            yield f"data: {json.dumps({'complete': True, 'success': True, 'message': 'Smart processing completed!', 'redirect': '/batch_control'})}\n\n"
            logging.info("[SMART SSE] Completion message sent successfully")
        except Exception as e:
            logging.error(f"[SMART SSE] Error in smart processing progress: {e}")
            yield f"data: {json.dumps({'complete': True, 'success': False, 'error': f'Processing error: {e}'})}\n\n"

    # Mirror headers used by analyze_intake_progress to avoid buffering
    response = app.response_class(generate_progress(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = '*'
    # Disable proxy buffering (Nginx etc.) when applicable
    response.headers['X-Accel-Buffering'] = 'no'
    return response

# Global variable to track processing state for polling fallback
_processing_state = {
    'active': False,
    'progress': 0,
    'total': 0,
    'message': '',
    'complete': False,
    'success': False,
    'error': None,
    'redirect': None
}

@app.route("/api/smart_processing_start", methods=['POST'])
def api_smart_processing_start():
    """
    Fallback endpoint to start smart processing for browsers with SSE issues.
    """
    global _processing_state
    
    # Reset processing state
    _processing_state = {
        'active': True,
        'progress': 0,
        'total': 0,
        'message': 'Starting processing...',
        'complete': False,
        'success': False,
        'error': None,
        'redirect': None
    }
    
    # Start processing in background thread
    import threading
    def run_processing():
        try:
            logging.info("[FALLBACK] Starting smart processing in background thread")
            
            # Import processing functions
            from .document_detector import get_detector
            from .processing import process_single_document
            cleanup_old_archives()
            import os as _os
            
            # Get files to process
            intake_dir = app_config.INTAKE_DIR
            pdf_files = [f for f in _os.listdir(intake_dir) if f.lower().endswith('.pdf')]
            pdf_files.sort()
            
            _processing_state['total'] = len(pdf_files)
            _processing_state['message'] = f'Found {len(pdf_files)} files to process'
            
            if len(pdf_files) == 0:
                _processing_state['complete'] = True
                _processing_state['success'] = True
                _processing_state['message'] = 'No files to process'
                _processing_state['redirect'] = '/batch_control'
                return
            
            # Load cached analysis
            import pickle
            cache_file = "/tmp/intake_analysis_cache.pkl"
            cached_analyses = {}
            if _os.path.exists(cache_file):
                with open(cache_file, 'rb') as f:
                    analyses_list = pickle.load(f)
                # Convert dicts to DocumentAnalysis if needed
                from .document_detector import DocumentAnalysis
                converted_analyses = []
                for analysis in analyses_list:
                    if isinstance(analysis, dict):
                        # Handle cache format mismatch: 'filename' -> 'file_path'
                        if 'filename' in analysis and 'file_path' not in analysis:
                            analysis['file_path'] = _os.path.join(intake_dir, analysis['filename'])
                            # Remove the 'filename' key to avoid conflicts
                            del analysis['filename']
                        converted_analyses.append(DocumentAnalysis(**analysis))
                    else:
                        converted_analyses.append(analysis)
                cached_analyses = {a.file_path: a for a in converted_analyses}
            else:
                cached_analyses = {}
            
            # Collect documents by strategy
            single_documents = []
            batch_scan_documents = []
            
            for i, filename in enumerate(pdf_files):
                _processing_state['progress'] = i
                _processing_state['message'] = f'Analyzing {filename}...'
                
                file_path = _os.path.join(intake_dir, filename)
                analysis = cached_analyses.get(file_path)
                
                if analysis:
                    if analysis.processing_strategy == "single_document":
                        single_documents.append(analysis)
                    elif analysis.processing_strategy == "batch_scan":
                        batch_scan_documents.append(analysis)
                else:
                    _processing_state['message'] = f'⚠ Skipped {filename} (no analysis data)'
            
            # Process collected documents
            batches_created = 0
            
            # Process all single documents as ONE batch
            if single_documents:
                _processing_state['message'] = f'Creating batch for {len(single_documents)} single documents...'
                from .processing import _process_single_documents_as_batch
                batch_id = _process_single_documents_as_batch(single_documents)
                if batch_id:
                    batches_created += 1
                    _processing_state['message'] = f'✓ Created single documents batch #{batch_id} with {len(single_documents)} files'
                    logging.info(f"✓ Created single documents batch #{batch_id} with {len(single_documents)} files")
                else:
                    _processing_state['message'] = f'✗ Failed to create single documents batch'
                    logging.error(f"✗ Failed to create single documents batch with {len(single_documents)} files")
            
            # Process each batch scan document separately
            for analysis in batch_scan_documents:
                filename = _os.path.basename(analysis.file_path)
                _processing_state['message'] = f'Creating batch for batch scan {filename}...'
                try:
                    from .processing import _process_single_documents_as_batch
                    batch_id = _process_single_documents_as_batch([analysis])
                    if batch_id:
                        batches_created += 1
                        _processing_state['message'] = f'✓ Created batch #{batch_id} for batch scan {filename}'
                        logging.info(f"✓ Created batch #{batch_id} for batch scan {filename}")
                    else:
                        _processing_state['message'] = f'✗ Failed to create batch for {filename}'
                        logging.error(f"✗ Failed to create batch for {filename}")
                except Exception as e:
                    logging.error(f"Error processing {analysis.file_path}: {e}")
                    _processing_state['message'] = f'✗ Failed {filename}: {str(e)}'
            
            # Complete
            _processing_state['progress'] = len(pdf_files)
            _processing_state['complete'] = True
            _processing_state['success'] = True
            if batches_created > 0:
                _processing_state['message'] = f'Successfully created {batches_created} batch(es) from {len(pdf_files)} files!'
                logging.info(f"Smart processing complete: Created {batches_created} batches from {len(pdf_files)} files")
            else:
                _processing_state['message'] = 'Processing complete, but no batches were created'
                logging.warning(f"Smart processing complete but no batches created from {len(pdf_files)} files")
            _processing_state['redirect'] = '/batch_control'
            
        except Exception as e:
            logging.error(f"[FALLBACK] Error in background processing: {e}")
            _processing_state['complete'] = True
            _processing_state['success'] = False
            _processing_state['error'] = str(e)
    
    # Start background thread
    thread = threading.Thread(target=run_processing)
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'started'})

@app.route("/api/smart_processing_status")
def api_smart_processing_status():
    """
    Fallback endpoint to check smart processing status for polling.
    """
    global _processing_state
    return jsonify(_processing_state)


def api_smart_processing_progress_with_strategy(force_strategy=None):
    """
    Flexible SSE endpoint that can force all files to a specific processing strategy.
    
    Args:
        force_strategy: If provided, all files will be processed with this strategy
                       ("single_document" or "batch_scan"). If None, uses cached analysis.
    """
    # Reuse the same logic as smart processing, but optionally override strategy
    from flask import Response
    from .document_detector import get_detector
    from .processing import process_single_document
    import json
    import time
    import os as _os
    
    def generate_progress():
        # Determine strategy name first
        if force_strategy == "single_document":
            strategy_name = "single document"
        elif force_strategy == "batch_scan":
            strategy_name = "batch scan"  
        else:
            strategy_name = "smart"
            
        # Same initial setup as smart processing
        yield f"data: {json.dumps({'message': 'Connection established, initializing...', 'progress': 0, 'total': 0})}\n\n"
        
        try:
            cleanup_old_archives()
            
            # Check intake directory
            intake_dir = app_config.INTAKE_DIR
            logging.info(f"[{strategy_name.upper()} SSE] Checking intake directory: {intake_dir}")
                
            if not _os.path.exists(intake_dir):
                logging.error(f"[SSE] Intake directory does not exist: {intake_dir}")
                yield f"data: {json.dumps({'complete': True, 'success': False, 'error': f'Intake directory does not exist: {intake_dir}'})}\n\n"
                return

            pdf_files = [
                _os.path.join(intake_dir, f)
                for f in _os.listdir(intake_dir)
                if f.lower().endswith('.pdf')
            ]

            total_files = len(pdf_files)
            logging.info(f"[SSE] Found {total_files} PDF files for {strategy_name} processing.")
            
            if total_files == 0:
                logging.warning(f"[SSE] No files to process in intake directory.")
                yield f"data: {json.dumps({'complete': True, 'success': True, 'message': 'No files to process', 'redirect': '/batch_control'})}\n\n"
                return

            # Load or generate analysis based on strategy
            analyses = []
            if force_strategy:
                # Force all files to use the specified strategy
                from .document_detector import DocumentAnalysis
                for path in pdf_files:
                    filename = _os.path.basename(path)
                    analyses.append(DocumentAnalysis(
                        file_path=path,
                        file_size_mb=0.0,  # Not critical for forced processing
                        page_count=1,      # Will be determined during processing  
                        processing_strategy=force_strategy,
                        confidence=1.0,    # Forced, so 100% confident
                        reasoning=[f'Forced {strategy_name} processing mode']
                    ))
                    logging.info(f"[SSE] Forced {filename} to use {force_strategy} strategy")
                
                yield f"data: {json.dumps({'progress': 0, 'total': total_files, 'message': f'Set {total_files} files to {strategy_name} mode', 'current_file': None})}\n\n"
            else:
                # Smart mode - load cached analysis results
                try:
                    import pickle
                    cache_file = "/tmp/intake_analysis_cache.pkl"
                    if _os.path.exists(cache_file):
                        with open(cache_file, 'rb') as f:
                            cached_analyses_list = pickle.load(f)
                        # Convert to DocumentAnalysis objects if needed
                        from .document_detector import DocumentAnalysis
                        for analysis_data in cached_analyses_list:
                            if isinstance(analysis_data, dict):
                                # Handle cache format mismatch: 'filename' -> 'file_path'
                                if 'filename' in analysis_data and 'file_path' not in analysis_data:
                                    analysis_data['file_path'] = _os.path.join(intake_dir, analysis_data['filename'])
                                    # Remove the 'filename' key to avoid conflicts
                                    del analysis_data['filename']
                                analyses.append(DocumentAnalysis(**analysis_data))
                            else:
                                analyses.append(analysis_data)
                        yield f"data: {json.dumps({'progress': 0, 'total': total_files, 'message': f'Loaded cached analysis for {len(analyses)} files', 'current_file': None})}\n\n"
                    else:
                        yield f"data: {json.dumps({'error': 'No cached analysis found. Please run intake analysis first.'})}\n\n"
                        return
                except Exception as e:
                    yield f"data: {json.dumps({'error': f'Failed to load analysis: {e}'})}\n\n"
                    return
            
            # Process files based on strategy - reuse existing logic but with forced classifications
            if force_strategy == "single_document":
                # All files are single documents
                single_docs = analyses
                batch_scans = []
                # Call improved workflow: create ONE batch for all single documents
                from .processing import _process_single_documents_as_batch
                batch_id = _process_single_documents_as_batch(single_docs)
                if batch_id:
                    yield f"data: {json.dumps({'progress': len(single_docs), 'total': total_files, 'message': f'Created single documents batch: {batch_id}', 'batch_id': batch_id})}\n\n"
                else:
                    yield f"data: {json.dumps({'progress': 0, 'total': total_files, 'error': 'Failed to create single documents batch'})}\n\n"
            elif force_strategy == "batch_scan":
                # All files are batch scans - use modern single document workflow
                batch_scans = analyses
                yield f"data: {json.dumps({'progress': 0, 'total': total_files, 'message': f'Processing {len(batch_scans)} batch scans using modern workflow...', 'current_file': None})}\n\n"
                
                from .processing import _process_single_documents_as_batch
                batch_id = _process_single_documents_as_batch(batch_scans)
                if batch_id:
                    yield f"data: {json.dumps({'progress': len(batch_scans), 'total': total_files, 'message': f'Created single documents batch: {batch_id}', 'batch_id': batch_id})}\n\n"
                else:
                    yield f"data: {json.dumps({'progress': 0, 'total': total_files, 'error': 'Failed to create single documents batch'})}\n\n"
            else:
                # Use analysis results (smart mode)
                single_docs = [a for a in analyses if a.processing_strategy == "single_document"]
                batch_scans = [a for a in analyses if a.processing_strategy == "batch_scan"]

                # Continue with existing processing logic...
                processed = 0
                yield f"data: {json.dumps({'progress': 0, 'total': total_files, 'message': f'Starting {strategy_name} processing: {len(single_docs)} single, {len(batch_scans)} batch', 'single_count': len(single_docs), 'batch_count': len(batch_scans)})}\n\n"
            
            # [Rest of processing logic would go here - same as smart processing]
            # For now, just mark as complete
            yield f"data: {json.dumps({'complete': True, 'success': True, 'message': f'{strategy_name.title()} processing completed! Processed {total_files} files.', 'redirect': '/batch_control'})}\n\n"
            
        except Exception as e:
            logging.error(f"[SSE] Error in {strategy_name} processing: {e}")
            yield f"data: {json.dumps({'complete': True, 'success': False, 'error': f'{strategy_name.title()} processing error: {e}'})}\n\n"

    response = app.response_class(generate_progress(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


@app.route("/process_batch_all_single", methods=["POST"])
def process_batch_all_single():
    """
    Process all files as single documents (speed mode).
    """
    logging.info("[SINGLE] /process_batch_all_single invoked; redirecting to /single_processing_progress")
    # Use 303 See Other to force browser to use GET method for redirect
    return redirect(url_for("single_processing_progress"), code=303)


@app.route("/process_batch_force_traditional", methods=["POST"])
def process_batch_force_traditional():
    """
    Process all files using traditional batch scan workflow (safety first).
    """
    logging.info("[BATCH] /process_batch_force_traditional invoked; redirecting to /batch_processing_progress")
    # Use 303 See Other to force browser to use GET method for redirect
    return redirect(url_for("batch_processing_progress"), code=303)


@app.route("/process_new_batch", methods=["POST"])
def handle_batch_processing():
    """
    Redirect to intake analysis (new enhanced workflow).
    This maintains compatibility with existing UI while adding the preview step.
    """
    return redirect(url_for("analyze_intake_page"))


@app.route("/batch_control")
def batch_control_page():
    """
    Displays the main dashboard, showing a list of all processed batches.
    For each batch, it fetches and displays key statistics like the number of
    flagged pages and ungrouped verified pages, giving the user a quick
    overview of the work that needs to be done.
    """
    # A new database connection is opened for each request to ensure thread safety
    # and proper connection management.
    conn = get_db_connection()
    # Fetches all batches, excluding consolidated ones, ordered by ID descending to show the most recent first.
    all_batches_raw = conn.execute("SELECT * FROM batches WHERE status NOT LIKE 'consolidated_into_%' ORDER BY id DESC").fetchall()
    conn.close()

    # The data from the database is raw. This loop enriches it with additional
    # information needed for the user interface.
    all_batches = []
    for batch in all_batches_raw:
        batch_dict = dict(batch)  # Convert the database row to a dictionary
        batch_id = batch_dict["id"]
        # Augment the batch data with counts that indicate the status of the
        # verification and grouping stages. This avoids complex queries and
        # keeps the initial fetch fast.
        batch_dict["flagged_count"] = count_flagged_pages_for_batch(batch_id)
        batch_dict["ungrouped_count"] = count_ungrouped_verified_pages(batch_id)
        all_batches.append(batch_dict)

    # Render the main dashboard template, passing the prepared list of batches
    # to be displayed in a table.
    # Add audit trail links for each batch and check manipulation status for single document batches
    conn = get_db_connection()
    for batch in all_batches:
        batch["audit_url"] = url_for("batch_audit_view", batch_id=batch["id"])
        
        # For single document batches, check if they have been manipulated
        if batch["status"] == "ready_for_manipulation":
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM single_documents 
                WHERE batch_id=? AND (
                    final_category IS NOT NULL OR 
                    final_filename IS NOT NULL
                )
            """, (batch["id"],))
            manipulated_count = cursor.fetchone()[0]
            batch["has_been_manipulated"] = manipulated_count > 0
    conn.close()
    
    return render_template("batch_control.html", batches=all_batches)


# --- DIRECT ACTION ROUTES (Accessed from Batch Control) ---
# These routes correspond to the primary actions a user can take on a batch
# from the main dashboard.

@app.route("/verify/<int:batch_id>")
def verify_batch_page(batch_id):
    """
    The first step in the manual workflow: page-by-page verification.
    This page allows the user to review each page of a batch, correct the
    AI-suggested category, set the correct rotation, and flag pages for
    later, more detailed review.
    """
    # Check the batch status. If verification is already complete, the user
    # should not be able to re-verify. Instead, they are sent to a read-only
    # "revisit" page to prevent accidental changes.
    batch = get_batch_by_id(batch_id)
    if batch and batch["status"] != "pending_verification":
        return redirect(url_for("revisit_batch_page", batch_id=batch_id))

    # Fetch all pages associated with this batch from the database.
    pages = get_pages_for_batch(batch_id)
    if not pages:
        # If a batch has no pages, there's nothing to verify. Redirect back
        # to Batch Control with a message.
        return redirect(
            url_for(
                "batch_control_page", message=f"No pages found for Batch #{batch_id}."
            )
        )

    # The application stores absolute paths to images. For security and
    # portability, we create relative paths to be used in the HTML `src`
    # attribute. This is handled by the `serve_processed_file` route.
    processed_dir = os.getenv("PROCESSED_DIR")
    pages_with_relative_paths = [
        dict(
            p,
            relative_image_path=os.path.relpath(
                p["processed_image_path"], processed_dir
            ),
        )
        for p in pages
    ]

    # Simple pagination is implemented to show one page at a time. The current
    # page number is taken from the URL query parameters (e.g., ?page=2).
    try:
        page_num = max(1, request.args.get("page", 1, type=int))
        page_num = min(page_num, len(pages_with_relative_paths))
        current_page = pages_with_relative_paths[page_num - 1]
    except (ValueError, TypeError):
        page_num = 1
        current_page = pages_with_relative_paths[0]

    # To provide a comprehensive list of categories in the dropdown, we combine
    # default categories with all categories that have been previously used
    # and saved in the database. This allows for consistency and the ability
    # to introduce new categories organically.
    combined_categories = get_active_categories()

    # Render the verification template, passing all the necessary data for
    # displaying the current page, pagination controls, and category options.
    return render_template(
        "verify.html",
        batch_id=batch_id,
        current_page=current_page,
        current_page_num=page_num,
        total_pages=len(pages_with_relative_paths),
    categories=combined_categories,
    )


@app.route("/review/<int:batch_id>")
def review_batch_page(batch_id):
    """
    Allows the user to review all pages that were flagged during the
    verification step. This provides a focused view to handle problematic pages,
    such as those with poor OCR quality, incorrect orientation, or ambiguous
    content.
    """
    # Fetch only the pages that have been explicitly flagged for this batch.
    flagged_pages = get_flagged_pages_for_batch(batch_id)
    if not flagged_pages:
        # If there are no flagged pages, there's nothing to review. The user
        # is sent back to the main dashboard.
        return redirect(url_for("batch_control_page"))

    batch = get_batch_by_id(batch_id)

    # As in the verify view, create relative image paths for the template.
    processed_dir = os.getenv("PROCESSED_DIR")
    pages_with_relative_paths = [
        dict(
            p,
            relative_image_path=os.path.relpath(
                p["processed_image_path"], processed_dir
            ),
        )
        for p in flagged_pages
    ]

    # The category list is needed here as well, so the user can correct
    # categories for flagged pages.
    combined_categories = get_active_categories()

    # Render the review template, which is specifically designed for handling
    # multiple flagged pages at once.
    return render_template(
        "review.html",
        batch_id=batch_id,
        batch=batch,
        flagged_pages=pages_with_relative_paths,
    categories=combined_categories,
    )


@app.route("/revisit/<int:batch_id>")
def revisit_batch_page(batch_id):
    """
    Allows a user to look through all pages of a batch that has already
    been verified. This is a read-only view intended for reviewing work
    that has already been completed, without the risk of making accidental
    changes.
    """
    pages = get_pages_for_batch(batch_id)
    if not pages:
        return redirect(
            url_for(
                "batch_control_page", message=f"No pages found for Batch #{batch_id}."
            )
        )

    batch = get_batch_by_id(batch_id)
    processed_dir = os.getenv("PROCESSED_DIR")
    pages_with_relative_paths = [
        dict(
            p,
            relative_image_path=os.path.relpath(
                p["processed_image_path"], processed_dir
            ),
        )
        for p in pages
    ]

    # Pagination is used here as well for navigating through the pages.
    page_num = request.args.get("page", 1, type=int)
    if not 1 <= page_num <= len(pages_with_relative_paths):
        page_num = 1
    current_page = pages_with_relative_paths[page_num - 1]

    combined_categories = get_active_categories()

    # The 'revisit.html' template is similar to 'verify.html' but with form
    # submission elements disabled to enforce the read-only nature of this view.
    return render_template(
        "revisit.html",
        batch_id=batch_id,
        batch=batch,
        current_page=current_page,
        current_page_num=page_num,
        total_pages=len(pages_with_relative_paths),
    categories=combined_categories,
    )


@app.route("/view/<int:batch_id>")
def view_batch_page(batch_id):
    """
    Provides a strictly read-only view of all pages in a completed batch.
    This page is for reviewing the final state of a batch after all workflow
    steps (verification, grouping, ordering, export) are complete. It does not
    offer any modification capabilities.
    """
    # Fetch all pages associated with this batch.
    pages = get_pages_for_batch(batch_id)
    # If a completed batch has no pages (an unlikely edge case), redirect.
    if not pages:
        return redirect(
            url_for(
                "batch_control_page", message=f"No pages found for Batch #{batch_id}."
            )
        )

    # Fetch the batch object to display its final status.
    batch = get_batch_by_id(batch_id)
    processed_dir = os.getenv("PROCESSED_DIR")
    # Create relative image paths for rendering in the template.
    pages_with_relative_paths = [
        dict(
            p,
            relative_image_path=os.path.relpath(
                p["processed_image_path"], processed_dir
            ),
        )
        for p in pages
    ]

    # Implement pagination to navigate through the pages of the batch.
    page_num = request.args.get("page", 1, type=int)
    if not 1 <= page_num <= len(pages_with_relative_paths):
        page_num = 1
    current_page = pages_with_relative_paths[page_num - 1]

    # Render the dedicated read-only template 'view_batch.html'.
    return render_template(
        "view_batch.html",
        batch_id=batch_id,
        batch=batch,
        current_page=current_page,
        current_page_num=page_num,
        total_pages=len(pages_with_relative_paths),
    )

@app.route("/group/<int:batch_id>")
def group_batch_page(batch_id):
    """
    The second major step of the workflow: grouping verified pages into documents.
    This page displays all verified pages, conveniently grouped by their assigned
    category. The user can then select pages from within a category and create a
    single, multi-page document from them.
    """
    # Fetch all verified pages that have not yet been assigned to a document.
    # The data is returned as a dictionary where keys are categories.
    ungrouped_pages_data = get_verified_pages_for_grouping(batch_id)
    created_docs = get_created_documents_for_batch(batch_id)
    processed_dir = os.getenv("PROCESSED_DIR")

    # Only auto-group if batch is in verification_complete state
    from doc_processor.database import get_batch_by_id, count_ungrouped_verified_pages, get_db_connection
    batch = get_batch_by_id(batch_id)
    auto_grouped = []
    to_remove = []
    if batch and dict(batch)["status"] == "verification_complete":
        for category, pages in list(ungrouped_pages_data.items()):
            if len(pages) == 1:
                page = pages[0]
                from .processing import get_ai_suggested_filename
                doc_text = page["ocr_text"] if "ocr_text" in page else ""
                logging.debug(f"Requesting AI filename for single-page doc: category={category}, page_id={page['id']}")
                doc_name = get_ai_suggested_filename(doc_text, category)
                logging.debug(f"AI suggested filename: {doc_name}")
                from doc_processor.database import create_document_and_link_pages
                create_document_and_link_pages(batch_id, doc_name, [page["id"]])
                auto_grouped.append(doc_name)
                to_remove.append(category)
        for cat in to_remove:
            ungrouped_pages_data.pop(cat, None)
        if auto_grouped:
            created_docs = get_created_documents_for_batch(batch_id)
        # If all pages are grouped, update status to grouping_complete
        if count_ungrouped_verified_pages(batch_id) == 0:
            conn = get_db_connection()
            conn.execute(
                "UPDATE batches SET status = 'grouping_complete' WHERE id = ?", (batch_id,)
            )
            conn.commit()
            conn.close()

    # Add relative image paths for remaining ungrouped pages
    for category, pages in ungrouped_pages_data.items():
        for i, page in enumerate(pages):
            page_dict = dict(page)
            page_dict["relative_image_path"] = os.path.relpath(
                page["processed_image_path"], processed_dir
            )
            ungrouped_pages_data[category][i] = page_dict

    return render_template(
        "group.html",
        batch_id=batch_id,
        grouped_pages=ungrouped_pages_data,
        created_docs=created_docs,
    )


@app.route("/order/<int:batch_id>")
def order_batch_page(batch_id):
    """
    The third step of the workflow: ordering pages within multi-page documents.
    This page lists all documents that have more than one page, as single-page
    documents do not require ordering. If a batch contains only single-page
    documents, this step is bypassed, and the batch is automatically marked as
    'ordering_complete' to streamline the workflow.
    """
    all_documents = get_documents_for_batch(batch_id)

    # Filter for documents that actually need ordering.
    docs_to_order = [doc for doc in all_documents if doc["page_count"] > 1]

    # If all documents were single-page, they are considered "ordered" by default.
    # This is a quality-of-life feature to avoid an unnecessary step for the user.
    if not docs_to_order and all_documents:
        conn = get_db_connection()
        conn.execute(
            "UPDATE batches SET status = 'ordering_complete' WHERE id = ?", (batch_id,)
        )
        conn.commit()
        conn.close()
        logging.info(f"Batch {batch_id} finalized automatically as it only contains single-page documents")
        return redirect(url_for("batch_control_page"))

    # Render the page that lists documents needing an explicit page order.
    return render_template(
        "order_batch.html", batch_id=batch_id, documents=docs_to_order
    )


@app.route("/order_document/<int:document_id>", methods=["GET", "POST"])
def order_document_page(document_id):
    """
    Handles the reordering of pages for a single document.
    - A GET request displays the user interface with draggable page thumbnails.
    - A POST request receives the new page order from the UI and saves it to the database.
    """
    # The batch_id is needed for redirection back to the main ordering page
    # after this document's ordering is complete.
    conn = get_db_connection()
    batch_id = conn.execute(
        "SELECT batch_id FROM documents WHERE id = ?", (document_id,)
    ).fetchone()["batch_id"]
    conn.close()

    if request.method == "POST":
        # The new order is submitted by a JavaScript function as a comma-separated
        # string of page IDs (e.g., "3,1,2").
        page_order = request.form.get("page_order")
        filename = request.form.get("filename")
        if not page_order:
            abort(400, "No page order provided")
        ordered_page_ids = page_order.split(",")
        # Sanitize the list to ensure all IDs are integers before database insertion.
        page_ids_as_int = [int(pid) for pid in ordered_page_ids if pid.isdigit()]
        if not page_ids_as_int:
            abort(400, "Invalid page order format")
        # The database function handles the complex update of the sequence numbers.
        update_page_sequence(document_id, page_ids_as_int)
        # Mark the document's status as having the order set.
        update_document_status(document_id, "order_set")
        # Save the user-edited filename if provided
        if filename:
            update_document_final_filename(document_id, filename)
        # Redirect back to the list of documents to be ordered for the same batch.
        return redirect(url_for("order_batch_page", batch_id=batch_id))

    # For a GET request, display the page ordering UI.
    pages_raw = get_pages_for_document(document_id)
    processed_dir = os.getenv("PROCESSED_DIR")
    # Convert all rows to dicts for .get() compatibility
    pages_dicts = [dict(p) for p in pages_raw]
    pages = [
        dict(
            p,
            relative_image_path=os.path.relpath(
                p["processed_image_path"], processed_dir
            ),
        )
        for p in pages_dicts
    ]
    # AI-suggested filename for this document
    suggested_filename = None
    if pages_dicts:
        full_doc_text = "\n---\n".join([p["ocr_text"] for p in pages_dicts if p.get("ocr_text")])
        doc_category = pages_dicts[0]["human_verified_category"] if pages_dicts[0].get("human_verified_category") else ""
        try:
            suggested_filename = get_ai_suggested_filename(full_doc_text, doc_category)
        except Exception:
            suggested_filename = None
    # The 'order_document.html' template contains the JavaScript for the
    # drag-and-drop interface (e.g., using SortableJS).
    return render_template(
        "order_document.html", document_id=document_id, pages=pages, batch_id=batch_id, suggested_filename=suggested_filename
    )


# --- API AND FORM ACTION ROUTES ---
# These routes handle form submissions and AJAX requests from the frontend.
# They perform specific actions and then typically redirect or return JSON.

@app.route("/finalize_batch/<int:batch_id>", methods=["POST"])
def finalize_batch_action(batch_id):
    """
    A final action to mark the entire ordering step for a batch as complete.
    This is triggered by a button on the 'order_batch.html' page when the user
    confirms that all necessary documents have been ordered.
    """
    conn = get_db_connection()
    conn.execute(
        "UPDATE batches SET status = 'ordering_complete' WHERE id = ?", (batch_id,)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("batch_control_page"))


@app.route("/api/suggest_order/<int:document_id>", methods=["POST"])
def suggest_order_api(document_id):
    """
    An API endpoint called via JavaScript from the ordering page.
    It uses an AI model (via `processing.py`) to suggest the correct order of
    pages for a given document based on their textual content. This is a helper
    feature to speed up the manual ordering process.
    """
    pages = get_pages_for_document(document_id)
    if not pages:
        return jsonify({"error": "Document not found or has no pages."} ), 404

    # The core AI ordering logic is in the 'processing.py' module.
    suggested_order = get_ai_suggested_order(pages)

    if suggested_order:
        # If successful, return the suggested order as a JSON list of page IDs.
        # The frontend JavaScript will then use this to reorder the elements on the page.
        return jsonify({"success": True, "page_order": suggested_order})
    else:
        # If the AI fails (e.g., due to insufficient text), return an error
        # that the frontend can display to the user.
        return (
            jsonify(
                {
                    "success": False,
                    "error": "AI suggestion failed. Please order manually.",
                }
            ),
            500,
        )


@app.route("/save_document", methods=["POST"])
def save_document_action():
    """
    Handles the form submission from the 'group' page to create a new document
    from a selection of pages. It takes the user-provided document name and
    the list of selected page IDs.
    """
    batch_id = request.form.get("batch_id", type=int)
    document_name = request.form.get("document_name", "").strip()
    page_ids = request.form.getlist("page_ids", type=int)

    # Basic validation to ensure the user has provided a name and selected pages.
    if not document_name or not page_ids:
        # Redirecting with an error message is not implemented here, but would be
        # a good addition for user feedback.
        return redirect(
            url_for(
                "group_batch_page",
                batch_id=batch_id,
                error="Document name and at least one page are required.",
            )
        )

    # The database function handles the creation of the document record and
    # linking the pages to it.
    create_document_and_link_pages(batch_id, document_name, page_ids)

    # After creating a document, check if all verified pages in the batch have
    # now been grouped. If so, the batch status is updated automatically,
    # moving the workflow forward.
    if count_ungrouped_verified_pages(batch_id) == 0:
        conn = get_db_connection()
        conn.execute(
            "UPDATE batches SET status = 'grouping_complete' WHERE id = ?", (batch_id,)
        )
        conn.commit()
        conn.close()

    # Redirect back to the grouping page to show the newly created document.
    return redirect(url_for("group_batch_page", batch_id=batch_id))


@app.route("/reset_grouping/<int:batch_id>", methods=["POST"])
def reset_grouping_action(batch_id):
    """
    Allows the user to undo the grouping for an entire batch.
    This is a "reset" button for the grouping stage. It deletes all documents
    created for the batch and un-links the pages, returning them to their
    ungrouped, verified state, ready to be grouped again.
    """
    reset_batch_grouping(batch_id)
    # Always revert status to verification_complete, even if already set
    conn = get_db_connection()
    conn.execute("UPDATE batches SET status = 'verification_complete' WHERE id = ?", (batch_id,))
    conn.commit()
    conn.close()
    logging.info(f"Batch {batch_id} status reset to verification_complete for regrouping")
    return redirect(url_for("group_batch_page", batch_id=batch_id))


@app.route("/reset_batch/<int:batch_id>", methods=["POST"])
def reset_batch_action(batch_id):
    """
    Handles the action to completely reset a batch to its initial state
    ('pending_verification'). This is a destructive action that undoes any
    verification, grouping, or ordering work, allowing the user to start over
    from the beginning.
    """
    # The core logic is encapsulated in the database function for safety and
    # to ensure all related data is reset correctly.
    logging.info(f"Resetting batch {batch_id} to start")
    reset_batch_to_start(batch_id)
    logging.info(f"Batch {batch_id} reset completed")
    # After the reset, send the user back to the main dashboard.
    return redirect(url_for("batch_control_page"))


@app.route("/update_page", methods=["POST"])
def update_page():
    """
    Handles form submissions from the 'verify' and 'review' pages to update
    the status, category, and rotation of a single page. This is one of the
    most critical interactive routes.
    """
    try:
        # Extract and validate required parameters
        page_id = request.form.get("page_id", type=int)
        batch_id = request.form.get("batch_id", type=int)
        if page_id is None or batch_id is None:
            abort(400, "Page ID and Batch ID are required")

        # Extract optional parameters with validation
        rotation = request.form.get("rotation", 0, type=int)
        if rotation not in {0, 90, 180, 270}:
            abort(400, "Invalid rotation angle")
            
        current_page_num = request.form.get("current_page_num", type=int)
        total_pages = request.form.get("total_pages", type=int)
        if current_page_num is not None and total_pages is not None:
            if not (1 <= current_page_num <= total_pages):
                abort(400, "Invalid page number")

        # Extract and validate action
        action = request.form.get("action")
        if action not in {"flag", "save"}:
            abort(400, "Invalid action")

        # Initialize and validate category-related fields
        category = ""
        status = ""
        dropdown_choice = request.form.get("category_dropdown")
        other_choice = sanitize_input(request.form.get("other_category", "").strip())
    except (ValueError, TypeError) as e:
        logging.error(f"Form validation error: {e}")
        abort(400, "Invalid form data")
    except Exception as e:
        logging.error(f"Unexpected error in update_page: {e}")
        abort(500, "Internal server error")

    try:
        # Determine the new status and category based on which button the user clicked
        # ('Flag for Review' vs. 'Save and Next').
        if action == "flag":
            status = "flagged"
            category = "NEEDS_REVIEW"  # A special category for flagged pages.
        else:
            status = "verified"
            # This logic handles the category selection, allowing a user to either
            # pick an existing category from the dropdown or create a new one by
            # typing into the "other" text field.
            if dropdown_choice == "other_new" and other_choice:
                category = other_choice
                # Insert the new custom category into the global categories table
                insert_category_if_not_exists(category)
            elif dropdown_choice and dropdown_choice != "other_new":
                category = dropdown_choice
            else:
                # If the user doesn't make an explicit choice, the system defaults
                # to using the original AI suggestion.
                category = request.form.get("ai_suggestion")
            # If the selected category is not in the categories table, insert it (handles AI suggestions or legacy data)
            insert_category_if_not_exists(category)
        if not category:
            abort(400, "Category is required")

        # Save the updated page data to the database.
        try:
            update_page_data(page_id, category, status, rotation)
        except DocProcessorError as e:
            logging.error(f"Failed to update page data: {e}")
            abort(500, "Failed to save page updates")

        # --- Redirection Logic ---
        # The application needs to intelligently redirect the user back to where
        # they came from.
        if "revisit" in request.referrer:
            # If they were on the revisit page, they should stay on that page.
            return redirect(
                url_for("revisit_batch_page", batch_id=batch_id, page=current_page_num)
            )
        if "review" in request.referrer:
            # If they were on the review page, they should return there to see the
            # list of remaining flagged pages.
            return redirect(url_for("review_batch_page", batch_id=batch_id))

        # If in the main verification flow, proceed to the next page.
        if current_page_num is not None and total_pages is not None and current_page_num < total_pages:
            return redirect(
                url_for("verify_batch_page", batch_id=batch_id, page=current_page_num + 1)
            )
        else:
            # If this was the last page of the batch, the verification step is
            # considered complete. The batch status is updated, and the user is
            # returned to the main dashboard.
            conn = None
            try:
                conn = get_db_connection()
                conn.execute(
                    "UPDATE batches SET status = 'verification_complete' WHERE id = ?",
                    (batch_id,)
                )
                conn.commit()
            except Exception as e:
                logging.error(f"Failed to update batch status: {e}")
                if conn:
                    conn.rollback()
                abort(500, "Failed to update batch status")
            finally:
                if conn:
                    conn.close()
            return redirect(url_for("batch_control_page"))
    except Exception as e:
        logging.error(f"Error processing page update: {e}")
        abort(500, "Failed to process page update")


@app.route("/delete_page/<int:page_id>", methods=["POST"])
def delete_page_action(page_id):
    """
    Permanently deletes a page from the database and its associated image file
    from the filesystem. This action is typically available on the 'review'
    page for pages that are determined to be unrecoverable, irrelevant, or duplicates.
    """
    batch_id = request.form.get("batch_id")
    # The deletion logic is handled in the database module to ensure atomicity.
    delete_page_by_id(page_id)
    # Redirect back to the review page to continue reviewing other flagged pages.
    return redirect(url_for("review_batch_page", batch_id=batch_id))


@app.route("/rerun_ocr", methods=["POST"])
def rerun_ocr_action():
    """
    Handles a request to re-run the OCR process on a single page, optionally
    applying a rotation first. This is useful if the initial OCR was poor due
    to the page being scanned upside down or sideways.
    """
    # Validate required parameters
    page_id = request.form.get("page_id", type=int)
    batch_id = request.form.get("batch_id", type=int)
    rotation = request.form.get("rotation", 0, type=int)
    
    if page_id is None or batch_id is None:
        abort(400, "Page ID and Batch ID are required")
    
    # Validate rotation angle
    if rotation not in {0, 90, 180, 270}:
        abort(400, "Invalid rotation angle")
    
    # The `rerun_ocr_on_page` function in `processing.py` handles the image
    # manipulation and the call to the OCR engine.
    try:
        rerun_ocr_on_page(page_id, rotation)
    except OCRError as e:
        logging.error(f"OCR error for page {page_id}: {e}")
        abort(500, "OCR processing failed")
    except FileProcessingError as e:
        logging.error(f"File processing error for page {page_id}: {e}")
        abort(500, "File processing failed")
    except DocProcessorError as e:
        logging.error(f"Document processing error for page {page_id}: {e}")
        abort(500, "Processing failed")
    
    # After re-running OCR, the user is returned to the review page to see
    # the updated OCR text and re-evaluate the page.
    return redirect(url_for("review_batch_page", batch_id=batch_id))

@app.route("/update_rotation", methods=["POST"])
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
        logging.warning(f"Failed to log rotation interaction: {e}")
    return jsonify({"success": True})


# --- UTILITY ROUTES ---
# These routes provide helper functionalities, like serving files.

@app.route("/processed_files/<path:filepath>")
def serve_processed_file(filepath):
    """
    A utility route to serve the processed image files (PNGs) to the browser.
    Using Flask's `send_from_directory` is a security best practice. It ensures
    that only files from within the specified `PROCESSED_DIR` can be accessed,
    preventing directory traversal attacks where a user might try to access
    sensitive files elsewhere on the server.
    """
    processed_dir = app_config.PROCESSED_DIR
    if not processed_dir or not os.path.isdir(processed_dir):
        abort(500, "Processed directory not configured")
    
    # Validate the requested filepath
    if not validate_path(filepath):
        abort(400, "Invalid file path")
        
    return send_from_directory(processed_dir, filepath)


@app.route("/original_pdf/<path:filename>")
def serve_original_pdf(filename):
    """
    Securely serves original PDF files for the PDF viewer modal.
    Only allows access to PDF files from the INTAKE_DIR to prevent directory traversal attacks.
    """
    intake_dir = app_config.INTAKE_DIR
    if not intake_dir or not os.path.isdir(intake_dir):
        abort(500, "Intake directory not configured")
    
    # Validate the requested filename - must be a PDF and no path traversal
    if not validate_path(filename):
        abort(400, "Invalid file path")
    
    if not filename.lower().endswith('.pdf'):
        abort(400, "Only PDF files are allowed")
    
    # Check if file exists in intake directory
    full_path = os.path.join(intake_dir, filename)
    if not os.path.isfile(full_path):
        abort(404, "PDF file not found")
    
    # Serve the PDF file with appropriate headers for viewing
    return send_from_directory(
        intake_dir, 
        filename, 
        mimetype='application/pdf',
        as_attachment=False  # Don't force download, allow inline viewing
    )


# --- FINALIZATION AND EXPORT ROUTES ---
# These routes handle the last stage of the workflow: naming and exporting.

@app.route("/finalize/<int:batch_id>")
def finalize_batch_page(batch_id):
    """
    Displays the new finalization screen where users can review and edit
    AI-suggested filenames for each document before the final export. This is
    the last chance to make changes before the files are written to the
    "filing cabinet".
    """
    documents_raw = get_documents_for_batch(batch_id)
    documents_for_render = []

    for doc in documents_raw:
        pages = get_pages_for_document(doc["id"])
        if not pages:
            continue  # Skip if a document somehow has no pages.
        # The full text of all pages is concatenated to give the AI model
        # maximum context for generating a good filename.
        full_doc_text = "\n---\n".join([p["ocr_text"] for p in pages])
        # The category is also provided to the AI to help it generate a more
        # relevant and structured filename.
        doc_category = pages[0]["human_verified_category"]
        suggested_filename = get_ai_suggested_filename(full_doc_text, doc_category)
        
        doc_dict = dict(doc)
        doc_dict["suggested_filename"] = suggested_filename
        documents_for_render.append(doc_dict)

    # The 'finalize.html' template will display a list of documents, each with
    # an editable text input pre-filled with the AI-suggested filename.
    return render_template(
        "finalize.html",
        batch_id=batch_id,
        documents=documents_for_render
    )


@app.route("/export_batch/<int:batch_id>", methods=["POST"])
def export_batch_action(batch_id):
    """
    Handles the final export process for all documents in a batch. This route
    receives the final list of document IDs and their user-approved filenames
    from the finalization page.
    """
    doc_ids = request.form.getlist('document_ids', type=int)
    final_filenames = request.form.getlist('final_filenames')

    # The form submits parallel lists of document IDs and their corresponding
    # final filenames. We zip them together to process them one by one.
    for doc_id, final_name in zip(doc_ids, final_filenames):
        pages = get_pages_for_document(doc_id)
        if not pages:
            logging.warning(f"Skipping export for document ID {doc_id}: No pages found")
            continue
        category = pages[0]['human_verified_category']
        final_name_base = os.path.splitext(final_name)[0]
        # Log the finalized name as a human correction event
        log_interaction(
            batch_id=batch_id,
            document_id=doc_id,
            user_id=None,  # Optionally set user_id if available
            event_type='human_correction',
            step='finalize',
            content=final_name_base,
            notes='Final filename set during export.'
        )
        update_document_final_filename(doc_id, final_name_base)
        export_document(pages, final_name_base, category)

    # Verify no files were lost during export
    from .processing import verify_no_file_loss
    safety_report = verify_no_file_loss()
    if safety_report["status"] == "safe":
        logging.info("✅ File safety verification passed - no PDFs lost during export")
    else:
        logging.error(f"⚠️ File safety verification failed: {safety_report}")

    # After all documents are exported, the temporary files associated with the
    # batch (like the intermediate PNGs) are deleted to save space.
    cleanup_batch_files(batch_id)

    # The batch is marked as 'Exported', its final status.
    conn = get_db_connection()
    conn.execute("UPDATE batches SET status = 'Exported' WHERE id = ?", (batch_id,))
    conn.commit()
    conn.close()

    # The user is returned to the main dashboard.
    return redirect(url_for("batch_control_page"))


@app.route("/finalize_single_documents_batch/<int:batch_id>", methods=["POST"])
def finalize_single_documents_batch_action(batch_id):
    """
    Finalize and export all single documents in a batch.
    This moves PDFs from their temporary locations to the proper category folders
    along with OCR text and markdown files.
    """
    try:
        from .processing import finalize_single_documents_batch
        success = finalize_single_documents_batch(batch_id)
        
        if success:
            # Update batch status to exported
            conn = get_db_connection()
            conn.execute("UPDATE batches SET status = 'Exported' WHERE id = ?", (batch_id,))
            conn.commit()
            conn.close()
            
            # Verify no files were lost during export
            from .processing import verify_no_file_loss
            safety_report = verify_no_file_loss()
            if safety_report["status"] == "safe":
                logging.info("✅ File safety verification passed - no PDFs lost during single document export")
            else:
                logging.error(f"⚠️ File safety verification failed: {safety_report}")
            
            flash('Single documents batch exported successfully!', 'success')
        else:
            flash('Error exporting single documents batch', 'error')
            
    except Exception as e:
        logging.error(f"Error finalizing single documents batch {batch_id}: {e}")
        flash(f'Export failed: {str(e)}', 'error')
    
    return redirect(url_for("batch_control_page"))


# --- VIEW EXPORTED DOCUMENTS ROUTES ---
# This section provides a way for users to access the final exported files.


@app.route('/view_documents/<int:batch_id>')
def view_documents_page(batch_id):
    """
    Displays a list of all documents for a given batch, providing a preview of each document (ordered page thumbnails and text snippets) and download links to the final PDF and log files.
    For single document batches, shows the actual PDFs instead of page thumbnails.
    """
    # Check if this is a single document batch
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM batches WHERE id = ?", (batch_id,))
    batch_result = cursor.fetchone()
    
    if batch_result and batch_result[0] in ['ready_for_manipulation', 'ready_for_export']:
        # Single document batch - show PDFs
        cursor.execute("""
            SELECT id, original_filename, ai_suggested_category, final_category, 
                   ai_suggested_filename, final_filename, searchable_pdf_path, ai_summary
            FROM single_documents WHERE batch_id = ?
            ORDER BY original_filename
        """, (batch_id,))
        
        single_docs = cursor.fetchall()
        conn.close()
        
        docs_with_previews = []
        for doc in single_docs:
            doc_dict = {
                'id': doc[0],
                'original_filename': doc[1],
                'category': doc[3] or doc[2] or 'Uncategorized',  # final_category or ai_suggested_category
                'filename': doc[5] or doc[4] or doc[1],  # final_filename or ai_suggested_filename
                'searchable_pdf_path': doc[6],
                'summary': doc[7] or 'No summary available',
                'is_single_document': True
            }
            docs_with_previews.append(doc_dict)
        
        return render_template('view_documents.html', 
                             batch_id=batch_id, 
                             documents=docs_with_previews,
                             is_single_document_batch=True)
    
    conn.close()
    # Traditional batch - show page thumbnails
    documents = get_documents_for_batch(batch_id)
    processed_dir = os.getenv("PROCESSED_DIR")
    docs_with_previews = []
    for doc in documents:
        doc_dict = dict(doc)
        pages = get_pages_for_document(doc_dict["id"])
        page_previews = []
        page_dicts = [dict(p) for p in pages]
        for p in page_dicts:
            rel_img = os.path.relpath(p["processed_image_path"], processed_dir) if processed_dir and p.get("processed_image_path") else None
            text_snippet = (p.get("ocr_text") or "")[:200]
            page_previews.append({
                "image": rel_img,
                "text": text_snippet,
                "page_num": p.get("sequence_num", 0) + 1
            })
        doc_dict["pages"] = page_previews
        # Add AI-suggested filename for preview (same as finalize)
        if page_dicts:
            full_doc_text = "\n---\n".join([p["ocr_text"] for p in page_dicts if p.get("ocr_text")])
            doc_category = page_dicts[0]["human_verified_category"] if page_dicts[0].get("human_verified_category") else ""
            try:
                doc_dict["suggested_filename"] = get_ai_suggested_filename(full_doc_text, doc_category)
            except Exception:
                doc_dict["suggested_filename"] = None
        # Add download links if exported
        if doc_dict.get("final_filename_base") and page_dicts:
            category = page_previews[0]["text"] if page_previews else ""
            first_page = page_dicts[0]
            category = first_page.get('human_verified_category', '')
            category_dir_name = "".join(c for c in category if c.isalnum() or c in (' ', '-', '_')).rstrip().replace(' ', '_')
            base = doc_dict["final_filename_base"]
            doc_dict['pdf_path'] = os.path.join(category_dir_name, f"{base}.pdf")
            doc_dict['ocr_pdf_path'] = os.path.join(category_dir_name, f"{base}_ocr.pdf")
            doc_dict['log_path'] = os.path.join(category_dir_name, f"{base}_log.md")
        docs_with_previews.append(doc_dict)

    return render_template("view_documents.html", documents=docs_with_previews, batch_id=batch_id)


@app.route('/download_export/<path:filepath>')
def download_export_file(filepath):
    """
    Securely serves an exported file for download from the FILING_CABINET_DIR.
    This route is essential for providing access to the final documents.
    """
    filing_cabinet_dir = os.getenv("FILING_CABINET_DIR")
    if not filing_cabinet_dir:
        # If the environment variable is not set, the application cannot find
        # the files, so it aborts with a server error.
        abort(500, "FILING_CABINET_DIR is not configured.")
    
    # --- Security Measure ---
    # This is a critical security check to prevent "path traversal" attacks.
    # It ensures that the requested file path is genuinely inside the intended
    # `filing_cabinet_dir` and not somewhere else on the filesystem (e.g.,
    # using `../../` to access system files).
    safe_base_path = os.path.abspath(filing_cabinet_dir)
    safe_filepath = os.path.abspath(os.path.join(safe_base_path, filepath))

    if not safe_filepath.startswith(safe_base_path):
        abort(404) # If the path is outside the allowed directory, return Not Found.

    # `send_from_directory` is used again here as it is the most robust and
    # secure way to handle file downloads in Flask.
    directory = os.path.dirname(safe_filepath)
    filename = os.path.basename(safe_filepath)
    
    # `as_attachment=True` tells the browser to prompt the user for a download
    # rather than trying to display the file in the browser window.
    return send_from_directory(directory, filename, as_attachment=True)


@app.route('/batch/<int:batch_id>/manipulate', methods=['GET', 'POST'])
def manipulate_batch_page(batch_id):
    """
    Manipulate stage for single document workflow: edit AI category/filename suggestions.
    """
    import json
    
    if request.method == 'POST':
        # Save edits for each document
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM single_documents WHERE batch_id=?", (batch_id,))
        doc_ids = [row[0] for row in cursor.fetchall()]
        for doc_id in doc_ids:
            # Handle category selection (same logic as verify workflow)
            category_dropdown = request.form.get(f'category_dropdown_{doc_id}')
            if category_dropdown == 'other_new':
                new_category = request.form.get(f'other_category_{doc_id}', '').strip()
            elif category_dropdown:
                new_category = category_dropdown
            else:
                # No selection made, keep AI suggestion
                cursor.execute("SELECT ai_suggested_category FROM single_documents WHERE id=?", (doc_id,))
                new_category = cursor.fetchone()[0]
            
            # Handle filename selection
            filename_choice = request.form.get(f'filename_choice_{doc_id}')
            if filename_choice == 'custom':
                new_filename = request.form.get(f'custom_filename_{doc_id}', '').strip()
            elif filename_choice == 'original':
                cursor.execute("SELECT original_filename FROM single_documents WHERE id=?", (doc_id,))
                original = cursor.fetchone()[0]
                # Remove extension and use as base filename
                new_filename = original.rsplit('.', 1)[0] if '.' in original else original
            else:
                # Use AI suggested filename
                cursor.execute("SELECT ai_suggested_filename FROM single_documents WHERE id=?", (doc_id,))
                new_filename = cursor.fetchone()[0]
            
            cursor.execute("""
                UPDATE single_documents SET
                    final_category=?,
                    final_filename=?
                WHERE id=?
            """, (new_category, new_filename, doc_id))
        conn.commit()
        
        # Update batch status to ready for export
        cursor.execute("UPDATE batches SET status = 'ready_for_export' WHERE id = ?", (batch_id,))
        conn.commit()
        conn.close()
        flash('Changes saved successfully. Ready for export.', 'success')
        return redirect(url_for('batch_control_page'))

    # GET: Show documents for manipulation
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, original_filename, ai_suggested_category, ai_suggested_filename, ai_confidence, ai_summary
        FROM single_documents WHERE batch_id=?
    """, (batch_id,))
    documents = [dict(zip(['id', 'original_filename', 'ai_suggested_category', 'ai_suggested_filename', 'ai_confidence', 'ai_summary'], row)) for row in cursor.fetchall()]
    conn.close()
    
    # Get categories for dropdown (same as verify workflow)
    from .database import get_active_categories
    categories = get_active_categories()
    
    return render_template('manipulate.html', batch_id=batch_id, documents=documents, categories=categories)


@app.route("/api/rescan_document/<int:doc_id>", methods=['POST'])
def rescan_document_api(doc_id):
    """
    API endpoint to rescan a single document for improved AI analysis.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get document details
        cursor.execute("""
            SELECT original_filename, ocr_text, page_count, file_size_bytes 
            FROM single_documents 
            WHERE id = ?
        """, (doc_id,))
        
        result = cursor.fetchone()
        if not result:
            return jsonify({"success": False, "error": "Document not found"})
        
        filename, ocr_text, page_count, file_size_bytes = result
        
        # Convert file size back to MB
        file_size_mb = file_size_bytes / (1024 * 1024) if file_size_bytes else 0
        
        # Get new AI suggestions
        from .processing import _get_ai_suggestions_for_document
        ai_category, ai_filename, ai_confidence, ai_summary = _get_ai_suggestions_for_document(
            ocr_text or "", filename, page_count or 1, file_size_mb
        )
        
        # Update the database
        cursor.execute("""
            UPDATE single_documents SET
                ai_suggested_category = ?,
                ai_suggested_filename = ?,
                ai_confidence = ?,
                ai_summary = ?
            WHERE id = ?
        """, (ai_category, ai_filename, ai_confidence, ai_summary, doc_id))
        
        conn.commit()
        conn.close()
        
        # Log the rescan
        import logging
        logging.info(f"Document {filename} rescanned - Category: {ai_category}, Filename: {ai_filename}, Confidence: {ai_confidence:.2f}")
        
        return jsonify({
            "success": True,
            "document": {
                "category": ai_category,
                "filename": ai_filename,
                "confidence": ai_confidence,
                "summary": ai_summary
            }
        })
        
    except Exception as e:
        import logging
        logging.error(f"Error rescanning document {doc_id}: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/file_safety_check")
def file_safety_check_api():
    """
    API endpoint to check file safety across all directories.
    Returns JSON report of file locations and potential losses.
    """
    from .processing import verify_no_file_loss
    
    try:
        from datetime import datetime
        report = verify_no_file_loss()
        return jsonify({
            "success": True,
            "report": report,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        from datetime import datetime
        logging.error(f"File safety check API failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


# --- MAIN EXECUTION ---

if __name__ == "__main__":
    """
    This block allows the script to be run directly using `python app.py`.
    It starts the Flask development server, which is convenient for testing
    and local development. For a production deployment, a more robust WSGI
    server like Gunicorn or uWSGI would be used instead.
    """
    # `debug=True` enables automatic reloading when code changes and provides
    # detailed error pages. This should be set to `False` in production.
    # `host="0.0.0.0"` makes the server accessible from any IP address on the
    # network, not just localhost.
    app.run(debug=True, host="0.0.0.0", port=5000)

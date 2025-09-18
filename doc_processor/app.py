import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from processing import process_batch, rerun_ocr_on_page, BROAD_CATEGORIES
from database import get_pages_for_batch, update_page_data, get_flagged_pages_for_batch, delete_page_by_id, get_all_unique_categories

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- DATABASE HELPER ---
def get_db_connection():
    db_path = os.getenv('DATABASE_PATH')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# --- FLASK ROUTES ---

@app.route('/')
def index():
    message = request.args.get('message')
    return render_template('index.html', message=message)

@app.route('/process_new_batch', methods=['POST'])
def handle_batch_processing():
    success = process_batch()
    if success:
        return redirect(url_for('verify_batch_entry'))
    else:
        return redirect(url_for('index', message="An error occurred during processing."))

# --- VERIFICATION ROUTES ---

@app.route('/verify')
def verify_batch_entry():
    """
    Finds the most recent batch that is still pending verification and redirects.
    """
    conn = get_db_connection()
    # MODIFIED: Look for the next batch that needs work
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM batches WHERE status = 'pending_verification' ORDER BY id DESC LIMIT 1")
    next_batch = cursor.fetchone()
    conn.close()

    if next_batch:
        return redirect(url_for('verify_batch_page', batch_id=next_batch['id']))
    else:
        return redirect(url_for('index', message="No batches are currently waiting for verification."))

@app.route('/verify/<int:batch_id>')
def verify_batch_page(batch_id):
    pages = get_pages_for_batch(batch_id)
    if not pages:
        return redirect(url_for('index', message=f"No pages found for Batch #{batch_id}."))

    processed_dir = os.getenv('PROCESSED_DIR')
    pages_with_relative_paths = [dict(p, relative_image_path=os.path.relpath(p['processed_image_path'], processed_dir)) for p in pages]

    page_num = request.args.get('page', 1, type=int)
    if page_num < 1: page_num = 1
    if page_num > len(pages_with_relative_paths): page_num = len(pages_with_relative_paths)
    current_page = pages_with_relative_paths[page_num - 1]
    
    db_categories = get_all_unique_categories()
    combined_categories = sorted(list(set(BROAD_CATEGORIES + db_categories)))
    
    return render_template('verify.html', 
                           batch_id=batch_id,
                           pages=pages_with_relative_paths,
                           current_page=current_page,
                           current_page_num=page_num,
                           total_pages=len(pages_with_relative_paths),
                           categories=combined_categories)

# --- REVIEW QUEUE ROUTES ---

@app.route('/review')
def review_batch_entry():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM batches ORDER BY id DESC LIMIT 1")
    last_batch = cursor.fetchone()
    conn.close()
    if last_batch:
        return redirect(url_for('review_batch_page', batch_id=last_batch['id']))
    else:
        return redirect(url_for('index', message="No batches found to review."))

@app.route('/review/<int:batch_id>')
def review_batch_page(batch_id):
    flagged_pages = get_flagged_pages_for_batch(batch_id)
    processed_dir = os.getenv('PROCESSED_DIR')
    pages_with_relative_paths = [dict(p, relative_image_path=os.path.relpath(p['processed_image_path'], processed_dir)) for p in flagged_pages]
    
    db_categories = get_all_unique_categories()
    combined_categories = sorted(list(set(BROAD_CATEGORIES + db_categories)))
    
    return render_template('review.html', 
                           batch_id=batch_id, 
                           flagged_pages=pages_with_relative_paths,
                           categories=combined_categories)

# --- ACTION ROUTES ---

@app.route('/update_page', methods=['POST'])
def update_page():
    action = request.form.get('action')
    page_id = request.form.get('page_id', type=int)
    batch_id = request.form.get('batch_id', type=int)
    rotation = request.form.get('rotation', 0, type=int)
    current_page_num = request.form.get('current_page_num', type=int)
    total_pages = request.form.get('total_pages', type=int)

    category = ''
    status = ''
    dropdown_choice = request.form.get('category_dropdown')
    other_choice = request.form.get('other_category', '').strip()

    if action == 'flag':
        status = 'flagged'
        category = 'NEEDS_REVIEW'
    else:
        status = 'verified'
        if dropdown_choice == 'other_new' and other_choice:
            category = other_choice
        elif dropdown_choice and dropdown_choice != 'other_new':
            category = dropdown_choice
        else:
            category = request.form.get('ai_suggestion')

    update_page_data(page_id, category, status, rotation)

    # MODIFIED: Logic to complete the batch
    if request.referrer and 'verify' in request.referrer and current_page_num == total_pages:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE batches SET status = 'verification_complete' WHERE id = ?", (batch_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('index', message=f"Batch #{batch_id} verification complete! You can now review flagged pages or start grouping."))

    # Redirect logic for review page
    if request.referrer and 'review' in request.referrer:
        return redirect(url_for('review_batch_page', batch_id=batch_id))
    
    # Default verification page behavior
    if current_page_num < total_pages:
        return redirect(url_for('verify_batch_page', batch_id=batch_id, page=current_page_num + 1))
    else:
        return redirect(url_for('index', message=f"Batch #{batch_id} verification complete!"))


@app.route('/delete_page/<int:page_id>', methods=['POST'])
def delete_page_action(page_id):
    batch_id = request.form.get('batch_id')
    delete_page_by_id(page_id)
    return redirect(url_for('review_batch_page', batch_id=batch_id))

@app.route('/rerun_ocr', methods=['POST'])
def rerun_ocr_action():
    page_id = request.form.get('page_id', type=int)
    batch_id = request.form.get('batch_id', type=int)
    rotation = request.form.get('rotation', 0, type=int)
    rerun_ocr_on_page(page_id, rotation)
    return redirect(url_for('review_batch_page', batch_id=batch_id))

@app.route('/processed_files/<path:filepath>')
def serve_processed_file(filepath):
    processed_dir = os.getenv('PROCESSED_DIR')
    return send_from_directory(processed_dir, filepath)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
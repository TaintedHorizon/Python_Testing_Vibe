import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from processing import process_batch, rerun_ocr_on_page, BROAD_CATEGORIES
from database import (
    get_pages_for_batch, update_page_data, get_flagged_pages_for_batch, 
    delete_page_by_id, get_all_unique_categories, get_verified_pages_for_grouping, 
    create_document_and_link_pages, get_created_documents_for_batch, get_batch_by_id,
    count_flagged_pages_for_batch, get_db_connection
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route('/')
def index():
    return redirect(url_for('mission_control_page'))

@app.route('/process_new_batch', methods=['POST'])
def handle_batch_processing():
    success = process_batch()
    return redirect(url_for('mission_control_page'))

@app.route('/mission_control')
def mission_control_page():
    conn = get_db_connection()
    all_batches_raw = conn.execute("SELECT * FROM batches ORDER BY id DESC").fetchall()
    conn.close()
    
    all_batches = []
    for batch in all_batches_raw:
        batch_dict = dict(batch)
        batch_dict['flagged_count'] = count_flagged_pages_for_batch(batch['id'])
        all_batches.append(batch_dict)

    return render_template('mission_control.html', batches=all_batches)

# --- DIRECT ACTION ROUTES ---
@app.route('/verify/<int:batch_id>')
def verify_batch_page(batch_id):
    batch = get_batch_by_id(batch_id)
    if batch and batch['status'] != 'pending_verification':
        return redirect(url_for('revisit_batch_page', batch_id=batch_id))
    pages = get_pages_for_batch(batch_id)
    if not pages: return redirect(url_for('mission_control_page', message=f"No pages found for Batch #{batch_id}."))
    processed_dir = os.getenv('PROCESSED_DIR')
    pages_with_relative_paths = [dict(p, relative_image_path=os.path.relpath(p['processed_image_path'], processed_dir)) for p in pages]
    page_num = request.args.get('page', 1, type=int)
    if not 1 <= page_num <= len(pages_with_relative_paths): page_num = 1
    current_page = pages_with_relative_paths[page_num - 1]
    db_categories = get_all_unique_categories()
    combined_categories = sorted(list(set(BROAD_CATEGORIES + db_categories)))
    return render_template('verify.html', batch_id=batch_id, current_page=current_page,
                           current_page_num=page_num, total_pages=len(pages_with_relative_paths),
                           categories=combined_categories)

@app.route('/review/<int:batch_id>')
def review_batch_page(batch_id):
    flagged_pages = get_flagged_pages_for_batch(batch_id)
    if not flagged_pages:
        return redirect(url_for('mission_control_page'))
    processed_dir = os.getenv('PROCESSED_DIR')
    pages_with_relative_paths = [dict(p, relative_image_path=os.path.relpath(p['processed_image_path'], processed_dir)) for p in flagged_pages]
    db_categories = get_all_unique_categories()
    combined_categories = sorted(list(set(BROAD_CATEGORIES + db_categories)))
    return render_template('review.html', batch_id=batch_id, 
                           flagged_pages=pages_with_relative_paths, categories=combined_categories)

@app.route('/revisit/<int:batch_id>')
def revisit_batch_page(batch_id):
    pages = get_pages_for_batch(batch_id)
    if not pages: return redirect(url_for('mission_control_page', message=f"No pages found for Batch #{batch_id}."))
    batch = get_batch_by_id(batch_id)
    processed_dir = os.getenv('PROCESSED_DIR')
    pages_with_relative_paths = [dict(p, relative_image_path=os.path.relpath(p['processed_image_path'], processed_dir)) for p in pages]
    page_num = request.args.get('page', 1, type=int)
    if not 1 <= page_num <= len(pages_with_relative_paths): page_num = 1
    current_page = pages_with_relative_paths[page_num - 1]
    db_categories = get_all_unique_categories()
    combined_categories = sorted(list(set(BROAD_CATEGORIES + db_categories)))
    return render_template('revisit.html', batch_id=batch_id, batch=batch,
                           current_page=current_page, current_page_num=page_num, 
                           total_pages=len(pages_with_relative_paths), categories=combined_categories)

@app.route('/group/<int:batch_id>')
def group_batch_page(batch_id):
    ungrouped_pages_data = get_verified_pages_for_grouping(batch_id)
    created_docs = get_created_documents_for_batch(batch_id)
    processed_dir = os.getenv('PROCESSED_DIR')
    for category, pages in ungrouped_pages_data.items():
        for i, page in enumerate(pages):
            page_dict = dict(page)
            page_dict['relative_image_path'] = os.path.relpath(page['processed_image_path'], processed_dir)
            ungrouped_pages_data[category][i] = page_dict
    return render_template('group.html', batch_id=batch_id,
                           grouped_pages=ungrouped_pages_data, created_docs=created_docs)

@app.route('/save_document', methods=['POST'])
def save_document_action():
    batch_id = request.form.get('batch_id', type=int)
    document_name = request.form.get('document_name', '').strip()
    page_ids = request.form.getlist('page_ids', type=int)
    if not document_name or not page_ids:
        return redirect(url_for('group_batch_page', batch_id=batch_id, error="Document name and at least one page are required."))
    create_document_and_link_pages(batch_id, document_name, page_ids)
    return redirect(url_for('group_batch_page', batch_id=batch_id))

@app.route('/update_page', methods=['POST'])
def update_page():
    action = request.form.get('action')
    page_id = request.form.get('page_id', type=int)
    batch_id = request.form.get('batch_id', type=int)
    rotation = request.form.get('rotation', 0, type=int)
    current_page_num = request.form.get('current_page_num', type=int)
    total_pages = request.form.get('total_pages', type=int)
    category = ''; status = ''
    dropdown_choice = request.form.get('category_dropdown')
    other_choice = request.form.get('other_category', '').strip()
    
    if action == 'flag':
        status = 'flagged'; category = 'NEEDS_REVIEW'
    else:
        status = 'verified'
        if dropdown_choice == 'other_new' and other_choice: category = other_choice
        elif dropdown_choice and dropdown_choice != 'other_new': category = dropdown_choice
        else: category = request.form.get('ai_suggestion')
    update_page_data(page_id, category, status, rotation)

    # Definitive Redirect Logic
    if 'revisit' in request.referrer:
        return redirect(url_for('revisit_batch_page', batch_id=batch_id, page=current_page_num))
    if 'review' in request.referrer:
        # After updating, check if any flagged pages remain
        remaining_flagged = get_flagged_pages_for_batch(batch_id)
        if not remaining_flagged:
            # If queue is empty, go back to mission control
            return redirect(url_for('mission_control_page'))
        else:
            # Otherwise, refresh the queue
            return redirect(url_for('review_batch_page', batch_id=batch_id))

    if current_page_num < total_pages:
        return redirect(url_for('verify_batch_page', batch_id=batch_id, page=current_page_num + 1))
    else:
        conn = get_db_connection()
        conn.execute("UPDATE batches SET status = 'verification_complete' WHERE id = ?", (batch_id,))
        conn.commit()
        conn.close()
        # After completing verification, check the review queue
        remaining_flagged = get_flagged_pages_for_batch(batch_id)
        if not remaining_flagged:
            # If no pages were flagged, go straight to grouping
            return redirect(url_for('group_batch_page', batch_id=batch_id))
        else:
            # Otherwise, go to the review queue as the next step
            return redirect(url_for('review_batch_page', batch_id=batch_id))

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
import sqlite3
import os
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

def get_db_connection():
    db_path = os.getenv('DATABASE_PATH')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def create_database():
    conn = get_db_connection()
    # ... (rest of function is unchanged) ...
    conn.close()

def get_pages_for_batch(batch_id):
    conn = get_db_connection()
    pages = conn.execute("SELECT * FROM pages WHERE batch_id = ? ORDER BY source_filename, page_number", (batch_id,)).fetchall()
    conn.close()
    return pages

def update_page_data(page_id, category, status, rotation):
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("UPDATE pages SET human_verified_category = ?, status = ?, rotation_angle = ? WHERE id = ?",
                         (category, status, rotation, page_id))
    except sqlite3.Error as e:
        print(f"Database error while updating page {page_id}: {e}")
    finally:
        if conn:
            conn.close()

def get_flagged_pages_for_batch(batch_id):
    conn = get_db_connection()
    pages = conn.execute("SELECT * FROM pages WHERE batch_id = ? AND status = 'flagged' ORDER BY id", (batch_id,)).fetchall()
    conn.close()
    return pages

def delete_page_by_id(page_id):
    conn = get_db_connection()
    try:
        with conn:
            image_path_row = conn.execute("SELECT processed_image_path FROM pages WHERE id = ?", (page_id,)).fetchone()
            if image_path_row:
                image_path = image_path_row['processed_image_path']
                conn.execute("DELETE FROM pages WHERE id = ?", (page_id,))
                if os.path.exists(image_path):
                    os.remove(image_path)
    except sqlite3.Error as e:
        print(f"Database error while deleting page {page_id}: {e}")
    finally:
        if conn:
            conn.close()

def get_all_unique_categories():
    conn = get_db_connection()
    results = conn.execute("SELECT DISTINCT human_verified_category FROM pages WHERE human_verified_category IS NOT NULL AND human_verified_category != '' ORDER BY human_verified_category").fetchall()
    conn.close()
    return [row['human_verified_category'] for row in results]

def get_batch_by_id(batch_id):
    conn = get_db_connection()
    batch = conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
    conn.close()
    return batch

def count_flagged_pages_for_batch(batch_id):
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) FROM pages WHERE batch_id = ? AND status = 'flagged'", (batch_id,)).fetchone()[0]
    conn.close()
    return count

def count_ungrouped_verified_pages(batch_id):
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) FROM pages p LEFT JOIN document_pages dp ON p.id = dp.page_id WHERE p.batch_id = ? AND p.status = 'verified' AND dp.page_id IS NULL", (batch_id,)).fetchone()[0]
    conn.close()
    return count

def get_verified_pages_for_grouping(batch_id):
    conn = get_db_connection()
    pages = conn.execute("SELECT p.* FROM pages p LEFT JOIN document_pages dp ON p.id = dp.page_id WHERE p.batch_id = ? AND p.status = 'verified' AND dp.page_id IS NULL ORDER BY p.human_verified_category, p.source_filename, p.page_number", (batch_id,)).fetchall()
    conn.close()
    grouped_pages = defaultdict(list)
    for page in pages:
        grouped_pages[page['human_verified_category']].append(page)
    return grouped_pages

def get_created_documents_for_batch(batch_id):
    conn = get_db_connection()
    documents = conn.execute("SELECT * FROM documents WHERE batch_id = ? ORDER BY created_at DESC", (batch_id,)).fetchall()
    conn.close()
    return documents

def create_document_and_link_pages(batch_id, document_name, page_ids):
    conn = get_db_connection()
    try:
        with conn:
            doc_id = conn.execute("INSERT INTO documents (batch_id, document_name) VALUES (?, ?)", (batch_id, document_name)).lastrowid
            page_data = [(doc_id, pid, i + 1) for i, pid in enumerate(page_ids)]
            conn.executemany("INSERT INTO document_pages (document_id, page_id, sequence) VALUES (?, ?, ?)", page_data)
    except sqlite3.Error as e:
        print(f"Database error during document creation: {e}")
    finally:
        if conn:
            conn.close()

def reset_batch_grouping(batch_id):
    """Deletes all document groups for a batch and resets its status."""
    conn = get_db_connection()
    try:
        with conn:
            docs_to_delete = conn.execute("SELECT id FROM documents WHERE batch_id = ?", (batch_id,)).fetchall()
            if docs_to_delete:
                doc_ids = [doc['id'] for doc in docs_to_delete]
                conn.execute(f"DELETE FROM document_pages WHERE document_id IN ({','.join(['?']*len(doc_ids))})", doc_ids)
                conn.execute("DELETE FROM documents WHERE batch_id = ?", (batch_id,))
            conn.execute("UPDATE batches SET status = 'verification_complete' WHERE id = ?", (batch_id,))
    except sqlite3.Error as e:
        print(f"Database error while resetting grouping for batch {batch_id}: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    create_database()
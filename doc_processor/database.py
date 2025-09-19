import sqlite3
import os
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

def create_database():
    db_path = os.getenv('DATABASE_PATH', 'documents.db')
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'pending_verification'
        );
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            source_filename TEXT,
            page_number INTEGER,
            processed_image_path TEXT,
            ocr_text TEXT,
            ai_suggested_category TEXT,
            human_verified_category TEXT,
            rotation_angle INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (batch_id) REFERENCES batches (id)
        );
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            document_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES batches (id)
        );
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS document_pages (
            document_id INTEGER,
            page_id INTEGER,
            sequence INTEGER,
            FOREIGN KEY (document_id) REFERENCES documents (id),
            FOREIGN KEY (page_id) REFERENCES pages (id),
            PRIMARY KEY (document_id, page_id)
        );
        ''')
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

def get_db_connection():
    db_path = os.getenv('DATABASE_PATH')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_pages_for_batch(batch_id):
    conn = get_db_connection()
    pages = conn.execute("SELECT * FROM pages WHERE batch_id = ? ORDER BY page_number", (batch_id,)).fetchall()
    conn.close()
    return pages

def update_page_data(page_id, category, status, rotation):
    db_path = os.getenv('DATABASE_PATH')
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE pages SET human_verified_category = ?, status = ?, rotation_angle = ? WHERE id = ?",
                     (category, status, rotation, page_id))
        conn.commit()
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
    db_path = os.getenv('DATABASE_PATH')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        image_path_row = cursor.execute("SELECT processed_image_path FROM pages WHERE id = ?", (page_id,)).fetchone()
        if image_path_row:
            image_path = image_path_row['processed_image_path']
            cursor.execute("DELETE FROM pages WHERE id = ?", (page_id,))
            conn.commit()
            if os.path.exists(image_path):
                os.remove(image_path)
    except sqlite3.Error as e:
        print(f"Database error while deleting page {page_id}: {e}")
    finally:
        conn.close()

def get_all_unique_categories():
    conn = get_db_connection()
    results = conn.execute("""
        SELECT DISTINCT human_verified_category FROM pages 
        WHERE human_verified_category IS NOT NULL AND human_verified_category != '' 
        ORDER BY human_verified_category
    """).fetchall()
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

def get_verified_pages_for_grouping(batch_id):
    conn = get_db_connection()
    pages = conn.execute("""
        SELECT p.* FROM pages p
        LEFT JOIN document_pages dp ON p.id = dp.page_id
        WHERE p.batch_id = ? AND p.status = 'verified' AND dp.page_id IS NULL
        ORDER BY p.human_verified_category, p.source_filename, p.page_number
    """, (batch_id,)).fetchall()
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
    db_path = os.getenv('DATABASE_PATH')
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            doc_id = conn.execute("INSERT INTO documents (batch_id, document_name) VALUES (?, ?)",
                                  (batch_id, document_name)).lastrowid
            page_data = [(doc_id, pid, i + 1) for i, pid in enumerate(page_ids)]
            conn.executemany("INSERT INTO document_pages (document_id, page_id, sequence) VALUES (?, ?, ?)",
                             page_data)
    except sqlite3.Error as e:
        print(f"Database error during document creation: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    create_database()
import sqlite3
import os
from dotenv import load_dotenv
from collections import defaultdict

# Load environment variables from .env file
load_dotenv()

def create_database():
    """
    Connects to the SQLite database and creates tables if they don't exist.
    """
    db_path = os.getenv('DATABASE_PATH', 'documents.db')
    db_dir = os.path.dirname(db_path)

    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"Created directory: {db_dir}")

    conn = None # Initialize conn to None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print(f"Successfully connected to database at '{db_path}'")

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'pending_verification'
        );
        ''')
        print("Table 'batches' created or already exists.")

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
        print("Table 'pages' created or already exists.")
        
        # Stores the final, assembled documents.
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            document_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES batches (id)
        );
        ''')
        print("Table 'documents' created or already exists.")

        # Links pages to their final document and defines their order.
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
        print("Table 'document_pages' created or already exists.")
        
        conn.commit()
        print("Database schema is up to date.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

def get_pages_for_batch(batch_id):
    """
    Retrieves all pages associated with a specific batch ID from the database.
    """
    db_path = os.getenv('DATABASE_PATH', 'documents.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pages WHERE batch_id = ? ORDER BY page_number", (batch_id,))
    pages = cursor.fetchall()
    conn.close()
    return pages

def update_page_data(page_id, category, status, rotation):
    """
    Updates the human-verified data for a single page.
    """
    db_path = os.getenv('DATABASE_PATH', 'documents.db')
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pages
            SET 
                human_verified_category = ?,
                status = ?,
                rotation_angle = ?
            WHERE id = ?
        """, (category, status, rotation, page_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error while updating page {page_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_flagged_pages_for_batch(batch_id):
    """
    Retrieves all pages marked with a 'flagged' status for a specific batch.
    """
    db_path = os.getenv('DATABASE_PATH', 'documents.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pages WHERE batch_id = ? AND status = 'flagged' ORDER BY id", (batch_id,))
    pages = cursor.fetchall()
    conn.close()
    return pages

def delete_page_by_id(page_id):
    """
    Deletes a page record from the database.
    """
    db_path = os.getenv('DATABASE_PATH', 'documents.db')
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT processed_image_path FROM pages WHERE id = ?", (page_id,))
        result = cursor.fetchone()
        if result:
            image_path = result[0]
            cursor.execute("DELETE FROM pages WHERE id = ?", (page_id,))
            conn.commit()
            if os.path.exists(image_path):
                os.remove(image_path)
                print(f"Deleted image file: {image_path}")
            return True
        else:
            print(f"No page found with ID: {page_id}")
            return False
    except sqlite3.Error as e:
        print(f"Database error while deleting page {page_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_all_unique_categories():
    """
    Retrieves a sorted list of all unique, non-null, non-empty 
    human-verified categories from the pages table.
    """
    db_path = os.getenv('DATABASE_PATH', 'documents.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT human_verified_category 
        FROM pages 
        WHERE human_verified_category IS NOT NULL AND human_verified_category != '' 
        ORDER BY human_verified_category
    """)
    results = [row[0] for row in cursor.fetchall()]
    conn.close()
    return results

# --- NEW FUNCTIONS FOR MODULE 3 ---
def get_verified_pages_for_grouping(batch_id):
    """
    Retrieves all verified pages for a batch, grouped by category.
    """
    db_path = os.getenv('DATABASE_PATH', 'documents.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    
    # Fetch only verified pages, ordered by category to group them together
    cursor.execute("""
        SELECT * FROM pages 
        WHERE batch_id = ? AND status = 'verified'
        ORDER BY human_verified_category, source_filename, page_number
    """, (batch_id,))
    pages = cursor.fetchall()
    conn.close()

    # Group the pages by category in a dictionary
    grouped_pages = defaultdict(list)
    for page in pages:
        grouped_pages[page['human_verified_category']].append(page)
        
    return grouped_pages

def create_document_and_link_pages(batch_id, document_name, page_ids):
    """
    Creates a new document and links the provided page IDs to it.
    """
    db_path = os.getenv('DATABASE_PATH', 'documents.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Start a transaction
        cursor.execute("BEGIN TRANSACTION")

        # 1. Create the new document
        cursor.execute(
            "INSERT INTO documents (batch_id, document_name) VALUES (?, ?)",
            (batch_id, document_name)
        )
        document_id = cursor.lastrowid
        print(f"Created document '{document_name}' with ID: {document_id}")

        # 2. Link pages to the new document
        for i, page_id in enumerate(page_ids):
            sequence = i + 1
            cursor.execute(
                "INSERT INTO document_pages (document_id, page_id, sequence) VALUES (?, ?, ?)",
                (document_id, page_id, sequence)
            )
        
        # Commit the transaction
        conn.commit()
        return document_id
        
    except sqlite3.Error as e:
        print(f"Database error during document creation: {e}")
        conn.rollback() # Roll back changes if an error occurs
        return None
    finally:
        conn.close()
# --- END OF NEW FUNCTIONS ---

if __name__ == '__main__':
    print("Initializing database setup...")
    create_database()
    print("Database setup complete.")
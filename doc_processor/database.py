import sqlite3
import os
from dotenv import load_dotenv

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
    # This makes the cursor return rows that can be accessed by column name
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
        # print(f"Successfully updated Page ID: {page_id}") # Optional: for debugging
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

    # The only change is "WHERE batch_id = ? AND status = 'flagged'"
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
        
        # First, get the image path so we can delete the file later
        cursor.execute("SELECT processed_image_path FROM pages WHERE id = ?", (page_id,))
        result = cursor.fetchone()
        if result:
            image_path = result[0]
            # Delete the database record
            cursor.execute("DELETE FROM pages WHERE id = ?", (page_id,))
            conn.commit()
            
            # Delete the actual image file from disk
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

if __name__ == '__main__':
    print("Initializing database setup...")
    create_database()
    print("Database setup complete.")

def get_all_unique_categories():
    """
    Retrieves a sorted list of all unique, non-null, non-empty 
    human-verified categories from the pages table.
    """
    db_path = os.getenv('DATABASE_PATH', 'documents.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # This query selects distinct categories, filtering out any that are null or just whitespace
    cursor.execute("""
        SELECT DISTINCT human_verified_category 
        FROM pages 
        WHERE human_verified_category IS NOT NULL AND human_verified_category != '' 
        ORDER BY human_verified_category
    """)
    
    # fetchall() returns a list of tuples, e.g., [('Category A',), ('Category B',)]
    # We convert it to a simple list: ['Category A', 'Category B']
    results = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return results
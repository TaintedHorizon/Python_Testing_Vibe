# doc_processor/reset_environment.py
import os
import sqlite3
import shutil
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
TABLES_TO_CLEAR = ["document_pages", "documents", "pages", "batches"]
CATEGORIES_BACKUP_FILE = "custom_categories_backup.json"
BROAD_CATEGORIES = [
    "Financial Document", "Legal Document", "Personal Correspondence",
    "Technical Document", "Medical Record", "Educational Material",
    "Receipt or Invoice", "Form or Application", "News Article or Publication",
    "Other",
]

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    db_path = os.getenv("DATABASE_PATH")
    if not db_path or not os.path.exists(db_path):
        print(f"[ERROR] Database path not found at '{db_path}'. Please check your .env file.")
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def backup_custom_categories(conn):
    """Saves custom categories to a JSON file."""
    print("--- Step 1: Backing up custom categories ---")
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT human_verified_category FROM pages WHERE human_verified_category IS NOT NULL")
        all_categories = {row[0] for row in cursor.fetchall() if row[0]}
        custom_categories = sorted(list(all_categories - set(BROAD_CATEGORIES)))
        
        if not custom_categories:
            print("No custom categories found to back up.")
            return

        with open(CATEGORIES_BACKUP_FILE, "w") as f:
            json.dump(custom_categories, f, indent=4)
        
        print(f"Successfully backed up {len(custom_categories)} custom categories to '{CATEGORIES_BACKUP_FILE}'")
        for cat in custom_categories:
            print(f"  - {cat}")
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to back up categories due to a database error: {e}")

def clear_database_tables(conn):
    """Deletes all records from the specified tables and resets the batch counter."""
    print("\n--- Step 2: Clearing database tables ---")
    try:
        cursor = conn.cursor()
        for table in TABLES_TO_CLEAR:
            print(f"  - Clearing table: {table}...")
            cursor.execute(f"DELETE FROM {table};")
        
        # *** NEW: Reset the autoincrement counter for the batches table ***
        print("  - Resetting batch ID counter...")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='batches';")

        conn.commit()
        print("All specified tables have been cleared and counters reset successfully.")
    except sqlite3.Error as e:
        print(f"[ERROR] An error occurred while clearing the database: {e}")
        conn.rollback()

def clear_test_directories():
    """
    Deletes the contents of the PROCESSED_DIR and FILING_CABINET_DIR using a robust method.
    """
    print("\n--- Step 3: Clearing test file directories ---")
    
    processed_dir = os.getenv("PROCESSED_DIR")
    filing_cabinet_dir = os.getenv("FILING_CABINET_DIR")
    
    paths_to_clear = set()
    if processed_dir: paths_to_clear.add(os.path.abspath(processed_dir))
    if filing_cabinet_dir: paths_to_clear.add(os.path.abspath(filing_cabinet_dir))

    def rmtree_error_handler(func, path, exc_info):
        """Error handler for shutil.rmtree that ignores FileNotFoundError."""
        if issubclass(exc_info[0], FileNotFoundError):
            print(f"  - Skipping non-existent path during cleanup: {path}")
        else:
            raise

    def clear_dir_contents(dir_path):
        if not os.path.isdir(dir_path):
            print(f"Skipping '{dir_path}': Directory not found or not configured.")
            return
        
        print(f"Clearing contents of '{dir_path}'...")
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path, onerror=rmtree_error_handler)
                print(f"  - Deleted: {item}")
            except Exception as e:
                print(f"  - [ERROR] Failed to delete {item_path}: {e}")
        print(f"Finished clearing '{dir_path}'.")

    for path in paths_to_clear:
        clear_dir_contents(path)

def main():
    """Main function to orchestrate the reset process."""
    print("Starting environment reset process...")
    
    confirm = input("This will delete all batches, documents, pages, and exported files. Are you sure you want to continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Operation cancelled.")
        return

    conn = get_db_connection()
    if conn:
        try:
            backup_custom_categories(conn)
            clear_database_tables(conn)
        finally:
            conn.close()
    
    clear_test_directories()
    
    print("\nEnvironment reset complete. You can now start a new test run.")

if __name__ == "__main__":
    main()
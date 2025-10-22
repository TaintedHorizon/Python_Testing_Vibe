# doc_processor/restore_categories.py
import os
import sqlite3
from doc_processor.dev_tools.db_connect import connect as db_connect
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
import tempfile
CATEGORIES_BACKUP_DIR = os.environ.get('CATEGORIES_BACKUP_DIR') or os.environ.get('DEV_TOOL_BACKUP_DIR') or tempfile.gettempdir()
CATEGORIES_BACKUP_FILE = os.path.join(CATEGORIES_BACKUP_DIR, "custom_categories_backup.json")
DUMMY_BATCH_STATUS = "template_batch"

import argparse
import sys
parser = argparse.ArgumentParser(description='Restore custom categories from backup into the DB (destructive)')
parser.add_argument('--dry-run', action='store_true', help='Show changes without applying them')
parser.add_argument('--yes', '-y', action='store_true', help='Auto-confirm destructive actions (or set CONFIRM_RESET=1)')
args = parser.parse_args()

dry_run = args.dry_run or os.getenv('DRY_RUN','0').lower() in ('1','true','t')
env_confirm = os.getenv('CONFIRM_RESET','0').lower() in ('1','true','t')
if not (env_confirm or args.yes):
    confirm = input("This will insert dummy batches/pages into the database to seed categories. Type 'yes' to continue: ")
    if confirm.lower() != 'yes':
        print("Operation cancelled (no confirmation).")
        sys.exit(0)

def get_db_connection():
    """Establishes a connection to the SQLite database using dev_tools.db_connect.connect.

    This respects the application's configured DB helper when the path matches,
    otherwise falls back to a direct sqlite3 connection.
    """
    db_path = os.getenv("DATABASE_PATH")
    if not db_path or not os.path.exists(db_path):
        print(f"[ERROR] Database path not found at '{db_path}'. Please check your .env file.")
        return None
    try:
        conn = db_connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        # As a last resort, direct sqlite3 connect
        try:
            # Use the helper as a final fallback as well for consistent behavior
            conn = db_connect(db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception:
            print("[ERROR] Failed to connect to the database using db_connect")
            return None

def main():
    """
    Reads custom categories from the backup JSON file and inserts them
    into the database by creating a special 'template_batch' with dummy pages.
    """
    print("--- Starting Custom Category Restore Process ---")

    # 1. Check if the backup file exists
    if not os.path.exists(CATEGORIES_BACKUP_FILE):
        print(f"[ERROR] Backup file '{CATEGORIES_BACKUP_FILE}' not found.")
        print("Please run 'reset_environment.py' on a populated database first to create the backup.")
        return

    # 2. Read the categories from the file
    try:
        with open(CATEGORIES_BACKUP_FILE, 'r') as f:
            custom_categories = json.load(f)
        if not custom_categories:
            print("Backup file is empty. No categories to restore.")
            return
        print(f"Found {len(custom_categories)} custom categories to restore.")
    except (IOError, json.JSONDecodeError) as e:
        print(f"[ERROR] Failed to read or parse '{CATEGORIES_BACKUP_FILE}': {e}")
        return

    # 3. Connect to the database
    conn = get_db_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()

        # 4. Check if a dummy batch for these categories already exists to avoid duplicates
        cursor.execute(
            "SELECT p.human_verified_category FROM pages p JOIN batches b ON p.batch_id = b.id WHERE b.status = ?",
            (DUMMY_BATCH_STATUS,)
        )
        existing_dummy_categories = {row[0] for row in cursor.fetchall()}

        categories_to_add = [cat for cat in custom_categories if cat not in existing_dummy_categories]

        if not categories_to_add:
            print("All custom categories already exist in a template batch. No action needed.")
            return

        print(f"Adding {len(categories_to_add)} new custom categories to the database...")

        # 5. Create a new dummy batch
        if dry_run:
            print("DRY-RUN: would create new template batch and insert dummy pages for categories")
            dummy_batch_id = None
        else:
            cursor.execute("INSERT INTO batches (status) VALUES (?)", (DUMMY_BATCH_STATUS,))
            dummy_batch_id = cursor.lastrowid
            print(f"Created new template batch with ID: {dummy_batch_id}")

        # 6. Insert a dummy page for each new custom category
        for category in categories_to_add:
            if dry_run:
                print(f"DRY-RUN: would add dummy page for category: '{category}'")
            else:
                cursor.execute(
                    """
                    INSERT INTO pages
                        (batch_id, source_filename, page_number, ocr_text, status, human_verified_category)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dummy_batch_id,
                        "template_file",
                        0,
                        f"Template page for category: {category}",
                        "template_page",
                        category
                    )
                )
                print(f"  - Added dummy page for category: '{category}'")

        # 7. Commit changes
        if dry_run:
            print("DRY-RUN: no changes were committed.")
        else:
            conn.commit()
            print("\nSuccessfully restored custom categories to the database.")

    except sqlite3.Error as e:
        print(f"[ERROR] A database error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
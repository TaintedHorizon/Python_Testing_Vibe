"""
This script is a developer-focused utility designed to solve a specific problem related to data persistence
after a full environment reset. It restores user-defined ("custom") categories into the database
from a JSON backup file (`custom_categories_backup.json`).

THE PROBLEM:
The application's user interface, specifically the category selection dropdowns, is populated dynamically.
It works by querying the `pages` table for all unique `human_verified_category` values. When a developer
runs the `reset_environment.py` script, the entire database is wiped clean. This means that any custom
categories a developer was using for testing (e.g., "Project Alpha Invoices") would be lost, and they
would have to manually process a document with that category again to make it reappear in the UI.

THE SOLUTION:
This script provides an automated way to repopulate these custom categories.
1.  It reads the list of custom category names from the JSON backup file (which is created by `reset_environment.py`).
2.  It creates a special, hidden "template" batch in the `batches` table.
3.  For each custom category name read from the backup, it inserts a single "dummy" page record into the `pages` table.
4.  This dummy page is associated with the template batch and its `human_verified_category` column is set to the category name.

This clever workaround ensures that when the application's UI queries for all unique categories, the restored
custom categories are found within these dummy records and are immediately available in the dropdowns after a reset,
streamlining the development and testing workflow.
"""
import os
import sqlite3
import json
from dotenv import load_dotenv

# Load environment variables from the .env file. This is used to get the database path.
load_dotenv()

# --- CONFIGURATION ---

# The constant filename for the JSON backup file. This file is expected to be created by `reset_environment.py`.
CATEGORIES_BACKUP_FILE = "custom_categories_backup.json"
# A unique status identifier for the dummy batch. This allows us to distinguish it from real, user-created batches
# and to easily find or clean up these template records later.
DUMMY_BATCH_STATUS = "template_batch"

def get_db_connection():
    """Establishes and returns a connection to the SQLite database."""
    # Retrieve the database file path from environment variables.
    db_path = os.getenv("DATABASE_PATH")
    # Perform a check to ensure the database path is configured and the file exists.
    if not db_path or not os.path.exists(db_path):
        print(f"[ERROR] Database path not found at '{db_path}'. Please check your .env file.")
        return None
    # Connect to the database.
    conn = sqlite3.connect(db_path)
    return conn

def main():
    """
    The main function that orchestrates the entire category restoration process.
    It is idempotent, meaning it can be run multiple times without creating duplicate entries.
    """
    print("--- Starting Custom Category Restore Process ---")

    # Step 1: Validate that the backup file exists before proceeding.
    if not os.path.exists(CATEGORIES_BACKUP_FILE):
        print(f"[ERROR] Backup file '{CATEGORIES_BACKUP_FILE}' not found.")
        print("Please run 'reset_environment.py' on a populated database first to create the backup.")
        return

    # Step 2: Read the custom category names from the JSON backup file.
    try:
        with open(CATEGORIES_BACKUP_FILE, 'r') as f:
            custom_categories = json.load(f)
        if not custom_categories:
            print("Backup file is empty. No categories to restore.")
            return
        print(f"Found {len(custom_categories)} custom categories in backup file.")
    except (IOError, json.JSONDecodeError) as e:
        print(f"[ERROR] Failed to read or parse '{CATEGORIES_BACKUP_FILE}': {e}")
        return

    # Step 3: Establish a connection to the database.
    conn = get_db_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()

        # Step 4: Check for existing dummy categories to avoid creating duplicates.
        # This makes the script safe to run multiple times (idempotent).
        # It queries for all categories that are already part of a template batch.
        cursor.execute(
            "SELECT p.human_verified_category FROM pages p JOIN batches b ON p.batch_id = b.id WHERE b.status = ?",
            (DUMMY_BATCH_STATUS,)
        )
        # Use a set for efficient lookup of existing categories.
        existing_dummy_categories = {row[0] for row in cursor.fetchall()}

        # Filter the list from the backup file to include only those categories that don't already exist in a template batch.
        categories_to_add = [cat for cat in custom_categories if cat not in existing_dummy_categories]

        if not categories_to_add:
            print("All custom categories from backup already exist in a template batch. No action needed.")
            return

        print(f"Adding {len(categories_to_add)} new custom categories to the database...")

        # Step 5: Create a single new dummy batch to hold all the new template pages.
        cursor.execute("INSERT INTO batches (status) VALUES (?)", (DUMMY_BATCH_STATUS,))
        # Get the ID of the newly created batch.
        dummy_batch_id = cursor.lastrowid
        print(f"Created new template batch with ID: {dummy_batch_id}")

        # Step 6: Insert a dummy page record for each new custom category.
        # This is the core of the solution. Each insertion creates a row in the `pages` table
        # that exists solely to hold the name of a custom category.
        for category in categories_to_add:
            cursor.execute(
                """
                INSERT INTO pages 
                    (batch_id, source_filename, page_number, ocr_text, status, human_verified_category) 
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    dummy_batch_id,      # Link the page to our new template batch.
                    "template_file",     # A placeholder filename.
                    0,                   # A placeholder page number.
                    f"Template page for category: {category}", # Descriptive placeholder text.
                    "template_page",     # A special status for easy identification.
                    category             # The actual custom category name we need to preserve.
                )
            )
            print(f"  - Added dummy page for category: '{category}'")
        
        # Step 7: Commit the transaction to save all changes to the database.
        conn.commit()
        print("\nSuccessfully restored custom categories to the database.")

    except sqlite3.Error as e:
        # If any database operation fails, print an error and roll back the transaction.
        print(f"[ERROR] A database error occurred: {e}")
        conn.rollback()
    finally:
        # Ensure the database connection is always closed, whether the operations succeeded or failed.
        conn.close()


# Standard Python entry point guard.
# This ensures that the `main()` function is called only when the script is executed directly from the command line.
if __name__ == "__main__":
    main()
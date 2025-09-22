"""
This script is a powerful and DESTRUCTIVE utility for developers to completely
reset the application's environment. It is designed to provide a clean slate
for testing and development by wiping the database and clearing out all
generated files.

*** WARNING: DO NOT RUN THIS SCRIPT IN A PRODUCTION ENVIRONMENT. ***
It will permanently delete all processed data.

The script performs the following actions in order:
1.  Connects to the database.
2.  Backs up any user-created "custom" categories to a JSON file so they can
    be restored later.
3.  Deletes all records from all major database tables.
4.  Resets the auto-incrementing counter for the 'batches' table.
5.  Deletes all files and subdirectories from the 'processed' and
    'filing cabinet' directories.
"""
# Import necessary standard libraries
import os  # Used for interacting with the operating system, like accessing environment variables and file paths.
import sqlite3  # The driver for the SQLite database, used for all database operations.
import shutil  # Provides high-level file operations, like recursively deleting directories.
import json  # Used for reading and writing the JSON backup file for custom categories.
from dotenv import load_dotenv  # Used to load configuration from a .env file into environment variables.

# Load environment variables from the .env file.
# This allows sensitive information like file paths to be stored securely and separately from the code.
load_dotenv()

# --- CONFIGURATION ---

# A list of database tables to be cleared.
# The order is chosen to respect potential foreign key relationships, although SQLite's DELETE command
# doesn't enforce these by default. Clearing child tables before parent tables is good practice.
TABLES_TO_CLEAR = ["document_pages", "documents", "pages", "batches"]

# Defines the constant filename for the JSON file that will store a backup of user-defined categories.
CATEGORIES_BACKUP_FILE = "custom_categories_backup.json"

# A hardcoded list of the default, broad categories provided by the application.
# This list is crucial for distinguishing between the system's standard categories and
# any "custom" categories that a user might have added.
BROAD_CATEGORIES = [
    "Financial Document", "Legal Document", "Personal Correspondence",
    "Technical Document", "Medical Record", "Educational Material",
    "Receipt or Invoice", "Form or Application", "News Article or Publication",
    "Other",
]

def get_db_connection():
    """
    Establishes and returns a connection to the SQLite database.
    
    This function retrieves the database file path from the environment variables.
    It checks if the database file actually exists before attempting to connect.
    If the path is not set or the file doesn't exist, it prints an error and returns None.
    
    Returns:
        sqlite3.Connection: A connection object to the database.
        None: If the database path is invalid or the file does not exist.
    """
    # Retrieve the database path from environment variables.
    db_path = os.getenv("DATABASE_PATH")
    # Check for the existence of the database file.
    if not db_path or not os.path.exists(db_path):
        print(f"[ERROR] Database path not found at '{db_path}'. Please run database_setup.py first.")
        return None
    # Connect to the SQLite database.
    conn = sqlite3.connect(db_path)
    # Set the row_factory to sqlite3.Row to allow accessing columns by name.
    conn.row_factory = sqlite3.Row
    return conn

def backup_custom_categories(conn):
    """
    Backs up user-created categories to a JSON file.
    
    This function queries the database for all unique, human-verified categories.
    It then filters out the default `BROAD_CATEGORIES` to isolate the custom ones.
    These custom categories are then saved to a JSON file, preserving them across resets.
    
    Args:
        conn (sqlite3.Connection): The active database connection.
    """
    print("--- Step 1: Backing up custom categories ---")
    try:
        # Create a cursor object to execute SQL queries.
        cursor = conn.cursor()
        # SQL query to select all distinct, non-null category names from the 'pages' table.
        cursor.execute("SELECT DISTINCT human_verified_category FROM pages WHERE human_verified_category IS NOT NULL")
        # Fetch all results and store them in a set for efficient processing.
        all_categories = {row[0] for row in cursor.fetchall() if row[0]}
        # Identify custom categories by finding the difference between all categories and the default ones.
        custom_categories = sorted(list(all_categories - set(BROAD_CATEGORIES)))

        # If there are no custom categories, there's nothing to do.
        if not custom_categories:
            print("No custom categories found to back up.")
            return

        # Write the sorted list of custom categories to the backup file in JSON format.
        with open(CATEGORIES_BACKUP_FILE, "w") as f:
            json.dump(custom_categories, f, indent=4)

        print(f"Successfully backed up {len(custom_categories)} custom categories to '{CATEGORIES_BACKUP_FILE}'")
        # Print the backed-up categories for user confirmation.
        for cat in custom_categories:
            print(f"  - {cat}")
    except sqlite3.Error as e:
        # Handle any potential database errors during the backup process.
        print(f"[ERROR] Failed to back up categories due to a database error: {e}")

def clear_database_tables(conn):
    """
    Deletes all data from specified tables and resets the batch ID counter.
    
    This function iterates through the `TABLES_TO_CLEAR` list and executes a
    `DELETE FROM` statement on each, effectively wiping their content. It also
    resets the auto-incrementing primary key for the 'batches' table so that
    the next new batch will start with ID 1.
    
    Args:
        conn (sqlite3.Connection): The active database connection.
    """
    print("\n--- Step 2: Clearing database tables ---")
    try:
        cursor = conn.cursor()
        # Loop through the list of tables to be cleared.
        for table in TABLES_TO_CLEAR:
            print(f"  - Clearing table: {table}...")
            # Execute the DELETE statement for the current table.
            cursor.execute(f"DELETE FROM {table};")

        # Reset the auto-increment counter for the 'batches' table.
        # In SQLite, this is done by deleting the table's entry from the `sqlite_sequence` table.
        print("  - Resetting batch ID counter...")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='batches';")

        # Commit all the changes to the database to make them permanent.
        conn.commit()
        print("All specified tables have been cleared and counters reset successfully.")
    except sqlite3.Error as e:
        # If any error occurs, print the error message and roll back the transaction.
        print(f"[ERROR] An error occurred while clearing the database: {e}")
        conn.rollback()

def clear_test_directories():
    """
    Deletes all files and subdirectories within the configured test directories.
    
    This function reads the paths for the 'processed' and 'filing cabinet' directories
    from the environment variables. It then iterates through all items in these
    directories and deletes them, ensuring a clean state for the next run.
    """
    print("\n--- Step 3: Clearing test file directories ---")

    # Get directory paths from environment variables.
    processed_dir = os.getenv("PROCESSED_DIR")
    filing_cabinet_dir = os.getenv("FILING_CABINET_DIR")

    # Use a set to handle cases where both variables might point to the same directory.
    paths_to_clear = set()
    if processed_dir: paths_to_clear.add(os.path.abspath(processed_dir))
    if filing_cabinet_dir: paths_to_clear.add(os.path.abspath(filing_cabinet_dir))

    def rmtree_error_handler(func, path, exc_info):
        """
        A custom error handler for `shutil.rmtree`.
        It ignores `FileNotFoundError`, which can occur in specific race conditions
        and is safe to ignore during a cleanup operation.
        """
        if issubclass(exc_info[0], FileNotFoundError):
            print(f"  - Skipping non-existent path during cleanup: {path}")
        else:
            # For any other type of error, re-raise it to be handled.
            raise

    def clear_dir_contents(dir_path):
        """A helper function to clear the contents of a single directory."""
        if not os.path.isdir(dir_path):
            print(f"Skipping '{dir_path}': Directory not found or not configured.")
            return

        print(f"Clearing contents of '{dir_path}'...")
        # List all items in the directory.
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            try:
                # Check if the item is a file or a symbolic link and delete it.
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                # Check if the item is a directory and delete it recursively.
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path, onerror=rmtree_error_handler)
                print(f"  - Deleted: {item}")
            except Exception as e:
                # Catch and report any other errors during deletion.
                print(f"  - [ERROR] Failed to delete {item_path}: {e}")
        print(f"Finished clearing '{dir_path}'.")

    # Iterate through the unique directory paths and clear them.
    for path in paths_to_clear:
        clear_dir_contents(path)

def main():
    """
    The main function to orchestrate the entire environment reset process.
    
    It includes a critical confirmation prompt to prevent accidental data deletion.
    It calls the functions to back up categories, clear the database, and clear
    the test directories in the correct order.
    """
    print("Starting environment reset process...")

    # A crucial safety measure: require explicit user confirmation before proceeding.
    confirm = input("This will delete all batches, documents, pages, and exported files. Are you sure you want to continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Operation cancelled.")
        return

    # Get a database connection.
    conn = get_db_connection()
    if conn:
        try:
            # Perform all database-related reset tasks.
            backup_custom_categories(conn)
            clear_database_tables(conn)
        finally:
            # Ensure the database connection is always closed, even if errors occur.
            conn.close()

    # Perform all file system-related reset tasks.
    clear_test_directories()

    print("\nEnvironment reset complete. You can now start a new test run.")

# Standard Python entry point.
# This ensures that the `main()` function is called only when the script is executed directly.
if __name__ == "__main__":
    main()
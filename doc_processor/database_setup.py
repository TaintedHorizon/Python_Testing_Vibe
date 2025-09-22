"""
This script, `database_setup.py`, is responsible for initializing the application's database.
It defines and creates the necessary SQLite database and tables required for the
document processing workflow. The script is designed to be idempotent, meaning
it can be run multiple times without causing errors or changing an already
correctly set up database.

The database schema is composed of four main tables:
- `batches`: Represents a collection of documents processed at one time.
- `pages`: Stores details for every single page extracted from the source files.
- `documents`: A logical grouping of one or more pages, created by the user.
- `document_pages`: A junction table that links pages to documents and defines
  their sequence within that document.

This script should be run once during the initial setup of the application.
"""
# Standard library imports
import sqlite3
import os

# Third-party imports
from dotenv import load_dotenv

# Load environment variables from a .env file into the environment.
# This allows for configurable settings, such as the database path, without
# hardcoding them. It's a best practice for separating configuration from code.
load_dotenv()


def create_database():
    """
    Connects to the SQLite database and creates the application's table schema.

    This function reads the DATABASE_PATH from the environment variables to
    determine where to create the database file. It ensures the directory for the
    database exists. Then, it executes a series of SQL `CREATE TABLE IF NOT EXISTS`
    statements. This command is safe to run on an existing database, as it will
    only create tables that are missing, leaving existing ones untouched.
    """
    # Get the database file path from environment variables. If DATABASE_PATH is
    # not set, it defaults to 'documents.db' in the current directory.
    db_path = os.getenv("DATABASE_PATH", "documents.db")
    # Extract the directory part of the path (e.g., 'instance' from 'instance/documents.db').
    db_dir = os.path.dirname(db_path)

    # If the database path includes a directory, this ensures that the directory
    # is created before attempting to connect to the database file within it.
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"Created directory: {db_dir}")

    conn = None  # Initialize conn to None for the finally block.
    try:
        # Connect to the database. SQLite creates the file if it doesn't exist.
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print(f"Successfully connected to database at '{db_path}'")

        # --- Create 'batches' table ---
        # A "batch" is the top-level organizational unit. It represents a single
        # run of the document processing pipeline, grouping all pages that were
        # processed together at a specific time.
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  -- A unique number for each batch.
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Records when the batch processing began.
            status TEXT NOT NULL DEFAULT 'processing' -- Tracks the batch's current stage in the workflow
                                                      -- (e.g., 'processing', 'pending_verification', 'grouping_complete', 'Exported').
        );
        """
        )
        print("Table 'batches' created or already exists.")

        # --- Create 'pages' table ---
        # This is the most detailed table, storing information about each individual
        # page extracted from the source files.
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, -- A unique identifier for every single page.
            batch_id INTEGER, -- Links this page back to the batch it belongs to.
            source_filename TEXT, -- The name of the original file (e.g., 'scan_01.pdf') this page came from.
            page_number INTEGER, -- The page number of this page within its original source file.
            processed_image_path TEXT, -- The absolute file path to the generated PNG image of the page.
            ocr_text TEXT, -- The full text extracted from the page by the OCR engine.
            ai_suggested_category TEXT, -- The initial category suggested by the AI analysis.
            human_verified_category TEXT, -- The category confirmed or corrected by the user during the verification step.
            status TEXT, -- The current status of the page (e.g., 'pending_verification', 'verified', 'flagged').
            rotation_angle INTEGER DEFAULT 0, -- The rotation (0, 90, 180, 270) applied by the user for correct orientation.
            FOREIGN KEY (batch_id) REFERENCES batches (id) -- Enforces that every page must belong to a valid batch.
        );
        """
        )
        print("Table 'pages' created or already exists.")

        # --- Create 'documents' table ---
        # A "document" is a logical entity created by a user during the 'grouping'
        # step. It represents a single, cohesive document that may be composed of
        # one or more pages.
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT, -- A unique identifier for each document.
            batch_id INTEGER, -- Links the document back to its original batch.
            document_name TEXT NOT NULL, -- The temporary name given to the document by the user during the grouping stage.
            status TEXT NOT NULL DEFAULT 'pending_order', -- Tracks the document's status (e.g., 'pending_order', 'order_set').
            final_filename_base TEXT, -- Stores the final, user-approved filename (without extension) before export.
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Records when the document was created.
            FOREIGN KEY (batch_id) REFERENCES batches (id) -- Enforces that every document must belong to a valid batch.
        );
        """
        )
        print("Table 'documents' created or already exists.")

        # --- Create 'document_pages' table (Junction Table) ---
        # This is a classic many-to-many junction table. It's the glue that
        # connects pages to the documents they belong to. It's necessary because
        # a document can have many pages, and in theory, a page could belong to
        # multiple documents (though not in this application's logic).
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS document_pages (
            document_id INTEGER, -- Foreign key referencing the 'documents' table.
            page_id INTEGER, -- Foreign key referencing the 'pages' table.
            sequence INTEGER, -- This is crucial: it defines the order of the page within the document (e.g., page 1, page 2, etc.).
            PRIMARY KEY (document_id, page_id), -- The primary key is a composite of both IDs, ensuring that a page can only be added to a document once.
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE, -- If a document is deleted, all its corresponding entries in this table are automatically removed.
            FOREIGN KEY (page_id) REFERENCES pages (id) ON DELETE CASCADE -- If a page is deleted (e.g., from the review screen), its link to any document is also automatically removed.
        );
        """
        )
        print("Table 'document_pages' created or already exists.")

        # Commit all the `CREATE TABLE` statements to the database, making the
        # changes permanent.
        conn.commit()
        print("Database schema is up to date.")

    except sqlite3.Error as e:
        # If any error occurs during the database operations, it will be caught
        # and printed to the console.
        print(f"Database error: {e}")
    finally:
        # The 'finally' block is guaranteed to execute, whether an error occurred
        # or not. This ensures that the database connection is always closed,
        # preventing resource leaks.
        if conn:
            conn.close()
            print("Database connection closed.")


# --- Main Execution Block ---
if __name__ == "__main__":
    """
    This standard Python construct checks if the script is being run directly
    by the user (e.g., `python database_setup.py`). If it is, it calls the
    `create_database()` function. This prevents the code from running if the
    script is imported as a module into another file.
    """
    print("Initializing database setup...")
    create_database()
    print("Database setup complete.")

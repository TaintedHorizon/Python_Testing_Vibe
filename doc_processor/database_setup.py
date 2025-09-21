# Standard library imports
import sqlite3
import os

# Third-party imports
from dotenv import load_dotenv

# Load environment variables from a .env file into the environment.
# This is used to get the database path, making the application more configurable.
load_dotenv()


def create_database():
    """
    Connects to the SQLite database specified by the DATABASE_PATH environment variable.
    It ensures that all necessary tables are created for the application to function.
    If the tables already exist, the script does nothing to them.
    This function is idempotent and safe to run multiple times.
    """
    # Get the database file path from environment variables, defaulting to 'documents.db'.
    db_path = os.getenv("DATABASE_PATH", "documents.db")
    # Get the directory part of the database path.
    db_dir = os.path.dirname(db_path)

    # If a directory is specified in the path (e.g., 'instance/documents.db'),
    # ensure that directory exists. If not, create it.
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"Created directory: {db_dir}")

    try:
        # conn is initialized here to be accessible in the 'finally' block.
        conn = None
        # Connect to the database. SQLite will create the file if it doesn't exist.
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print(f"Successfully connected to database at '{db_path}'")

        # --- Create 'batches' table ---
        # A batch represents a single processing run, initiated when the user clicks
        # the "Process New Batch" button. It groups all pages processed at that time.
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Unique identifier for the batch.
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- When the batch processing began.
            status TEXT NOT NULL DEFAULT 'processing' -- The current stage of the batch in the workflow (e.g., 'processing', 'pending_verification', 'complete').
        );
        """
        )
        print("Table 'batches' created or already exists.")

        # --- Create 'pages' table ---
        # This table stores information about each individual page extracted from the source PDFs.
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, -- Unique identifier for each page.
            batch_id INTEGER, -- Foreign key linking the page to a specific batch.
            source_filename TEXT, -- The name of the original PDF file this page came from.
            page_number INTEGER, -- The page number within the original PDF.
            processed_image_path TEXT, -- The path to the saved PNG image of the page.
            ocr_text TEXT, -- The full text extracted from the page by the OCR engine.
            ai_suggested_category TEXT, -- The category suggested by the AI model.
            human_verified_category TEXT, -- The category confirmed or corrected by the user.
            status TEXT, -- The current status of the page (e.g., 'pending_verification', 'verified', 'flagged').
            rotation_angle INTEGER DEFAULT 0, -- The rotation applied to the image for correct OCR, in degrees.
            FOREIGN KEY (batch_id) REFERENCES batches (id) -- Enforces the link to the 'batches' table.
        );
        """
        )
        print("Table 'pages' created or already exists.")

        # --- Create 'documents' table ---
        # A document is a logical grouping of one or more pages, created by the user
        # during the 'grouping' step of the workflow.
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT, -- Unique identifier for the document.
            batch_id INTEGER, -- Foreign key linking the document to its original batch.
            document_name TEXT NOT NULL, -- The name given to the document by the user.
            status TEXT NOT NULL DEFAULT 'pending_order', -- The status of the document (e.g., 'pending_order', 'order_set').
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- When the document was created.
            FOREIGN KEY (batch_id) REFERENCES batches (id) -- Enforces the link to the 'batches' table.
        );
        """
        )
        print("Table 'documents' created or already exists.")

        # --- Create 'document_pages' table (Junction Table) ---
        # This is a many-to-many junction table that links pages to documents.
        # It also stores the sequence of pages within a document.
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS document_pages (
            document_id INTEGER, -- Foreign key to the 'documents' table.
            page_id INTEGER, -- Foreign key to the 'pages' table.
            sequence INTEGER, -- The order of this page within the document (e.g., 1, 2, 3...).
            PRIMARY KEY (document_id, page_id), -- Ensures a page can only be in a document once.
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE, -- If a document is deleted, its page links are also deleted.
            FOREIGN KEY (page_id) REFERENCES pages (id) ON DELETE CASCADE -- If a page is deleted, its link to a document is also deleted.
        );
        """
        )
        print("Table 'document_pages' created or already exists.")

        # Commit all the table creation statements to the database.
        conn.commit()
        print("Database schema is up to date.")

    except sqlite3.Error as e:
        # Catch and print any SQLite-specific errors that occur.
        print(f"Database error: {e}")
    finally:
        # The 'finally' block ensures that the database connection is closed,
        # even if an error occurred.
        if conn:
            conn.close()
            print("Database connection closed.")


# --- Main Execution Block ---
if __name__ == "__main__":
    """
    This block is executed only when the script is run directly from the command line
    (e.g., 'python database_setup.py'). It is the entry point for setting up the database.
    """
    print("Initializing database setup...")
    create_database()
    print("Database setup complete.")
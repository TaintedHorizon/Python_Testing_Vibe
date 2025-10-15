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
    # Resolve database path: prefer env DATABASE_PATH, then app_config, then repo-local fallback.
    db_path = os.getenv('DATABASE_PATH')
    if not db_path:
        try:
            from ..config_manager import app_config
            db_path = getattr(app_config, 'DATABASE_PATH', None)
        except Exception:
            db_path = None
    if not db_path:
        db_path = os.path.join(os.path.dirname(__file__), '..', 'documents.db')
    print(f"[SETUP] Using database file: {os.path.abspath(db_path)}")
    # Get the directory part of the database path.
    db_dir = os.path.dirname(db_path)

    # If a directory is specified in the path (e.g., 'instance/documents.db'),
    # ensure that directory exists. If not, create it.
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"Created directory: {db_dir}")

    from doc_processor.dev_tools.db_connect import connect as db_connect
    conn = None
    def _connect(path):
        """Connect to DB: prefer centralized helper when path matches configured DB."""
        try:
            return db_connect(path, timeout=30.0)
        except Exception:
            from .db_connect import connect as db_connect
            return db_connect(path, timeout=30.0)

    try:
        # Prefer the application's centralized DB helper when running inside
        # the app context. This applies PRAGMA settings and safety guards.
        conn = _connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        print(f"Successfully connected to database at '{os.path.abspath(db_path)}'")

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
            status TEXT NOT NULL DEFAULT 'pending_order' -- The status of the document (e.g., 'pending_order', 'order_set').
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


        # --- Create 'categories' table ---
        # This table stores the predefined list of document categories that the
        # user can assign to documents.
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, -- A unique identifier for each category.
            name TEXT NOT NULL UNIQUE, -- The name of the category (e.g., "Financial Document"). The UNIQUE constraint prevents duplicate category names.
            is_active BOOLEAN NOT NULL DEFAULT 1, -- True if category is active and shown in dropdowns, False if removed.
            previous_name TEXT, -- Stores old name if category is renamed.
            notes TEXT -- Optional notes for admin/LLM training.
        );
        """
        )
        print("Table 'categories' created or already exists.")

        # --- Create 'interaction_log' table ---
        # This table logs every AI prompt/response, human correction, and status change for RAG and audit.
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS interaction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, -- Unique identifier for the log entry.
            batch_id INTEGER, -- Foreign key referencing the batch.
            document_id INTEGER, -- Foreign key referencing the document (nullable for batch-level events).
            user_id TEXT, -- User identifier (nullable).
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- When the event occurred.
            event_type TEXT NOT NULL, -- 'ai_prompt', 'ai_response', 'human_correction', 'status_change', etc.
            step TEXT, -- Workflow step: 'verify', 'review', 'group', 'order', 'name', etc.
            content TEXT, -- The prompt, response, correction, or status info (JSON or text).
            notes TEXT, -- Optional extra context.
            FOREIGN KEY (batch_id) REFERENCES batches (id),
            FOREIGN KEY (document_id) REFERENCES documents (id)
        );
        """
        )
        print("Table 'interaction_log' created or already exists.")

        # --- Create 'category_change_log' table ---
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS category_change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            action TEXT NOT NULL, -- add, rename, soft_delete, restore
            old_name TEXT,
            new_name TEXT,
            notes TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        );
        """
        )
        print("Table 'category_change_log' created or already exists.")

        # --- Seed Initial Categories ---
        # This section populates the 'categories' table with a default set of
        # document types. It uses an INSERT OR IGNORE statement to prevent errors
        # if the categories already exist, making the seeding operation safe to
        # run multiple times.
        initial_categories = [
            "Financial Document",
            "Legal Document",
            "Personal Correspondence",
            "Technical Document",
            "Medical Record",
            "Educational Material",
            "Receipt or Invoice",
            "Form or Application",
            "News Article or Publication",
            "Other",
        ]
        # executemany is an efficient way to insert multiple rows at once.
        # The list comprehension creates a list of tuples, as required by executemany.
        cursor.executemany(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)",
            [(cat,) for cat in initial_categories],
        )
        print("Default categories seeded or already exist.")

        # Commit all the `CREATE TABLE` and `INSERT` statements to the database,
        # making the changes permanent.
        # --- Additional modern tables / columns (idempotent) ---
        # single_documents: newer single-document workflow table
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS single_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            source_filename TEXT,
            final_category TEXT,
            final_filename TEXT,
            searchable_pdf_path TEXT,
            ocr_text TEXT,
            ocr_confidence_avg REAL,
            ai_confidence REAL,
            ai_summary TEXT,
            page_count INTEGER,
            file_size_bytes INTEGER,
            status TEXT DEFAULT 'pending',
            final_category_locked INTEGER DEFAULT 0,
            ai_filename_source_hash TEXT,
            ocr_source_signature TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(batch_id) REFERENCES batches(id) ON DELETE CASCADE
        );
        """
        )
        print("Table 'single_documents' created or already exists.")

        # document_tags: extracted metadata / tag storage with uniqueness constraint
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS document_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            tag_category TEXT,
            tag_value TEXT,
            llm_source TEXT,
            extraction_confidence REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(document_id, tag_category, tag_value),
            FOREIGN KEY(document_id) REFERENCES single_documents(id) ON DELETE CASCADE
        );
        """
        )
        print("Table 'document_tags' created or already exists.")

        # tag_usage_stats: summary/aggregation for tag usage patterns
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS tag_usage_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_category TEXT,
            tag_value TEXT,
            usage_count INTEGER DEFAULT 0,
            last_used TIMESTAMP
        );
        """
        )
        print("Table 'tag_usage_stats' created or already exists.")

        # Ensure new columns exist on existing tables (best-effort):
        def table_has_column(tbl, col):
            try:
                rows = cursor.execute(f"PRAGMA table_info({tbl})").fetchall()
                return any(r[1] == col for r in rows)
            except Exception:
                return False

        # documents.final_filename_base
        if not table_has_column('documents', 'final_filename_base'):
            try:
                cursor.execute("ALTER TABLE documents ADD COLUMN final_filename_base TEXT")
                print("Added column 'final_filename_base' to 'documents'")
            except Exception:
                pass

        # batches.has_been_manipulated
        if not table_has_column('batches', 'has_been_manipulated'):
            try:
                cursor.execute("ALTER TABLE batches ADD COLUMN has_been_manipulated INTEGER DEFAULT 0")
                print("Added column 'has_been_manipulated' to 'batches'")
            except Exception:
                pass

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
            try:
                conn.close()
            except Exception:
                pass
            print("Database connection closed.")


# --- Main Execution Block ---
if __name__ == "__main__":
    print("Initializing database setup...")
    create_database()
    print("Database setup complete.")
    print("Database setup complete.")
import sqlite3
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def create_database():
    """
    Connects to the SQLite database specified in the .env file,
    creates the necessary tables if they don't already exist,
    and then closes the connection.
    """
    db_path = os.getenv("DATABASE_PATH", "documents.db")
    db_dir = os.path.dirname(db_path)

    # Create the directory for the database if it doesn't exist
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"Created directory: {db_dir}")

    try:
        # Connect to the database (this will create the file if it doesn't exist)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print(f"Successfully connected to database at '{db_path}'")

        # --- Create 'batches' table ---
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'processing'
        );
        """
        )
        print("Table 'batches' created or already exists.")

        # --- Create 'pages' table ---
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            source_filename TEXT,
            page_number INTEGER,
            processed_image_path TEXT,
            ocr_text TEXT,
            ai_suggested_category TEXT,
            human_verified_category TEXT,
            status TEXT,
            rotation_angle INTEGER DEFAULT 0,
            FOREIGN KEY (batch_id) REFERENCES batches (id)
        );
        """
        )
        print("Table 'pages' created or already exists.")

        # --- Create 'documents' table (Corrected Version) ---
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            document_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending_order',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES batches (id)
        );
        """
        )
        print("Table 'documents' created or already exists.")

        # --- Create 'document_pages' table ---
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS document_pages (
            document_id INTEGER,
            page_id INTEGER,
            sequence INTEGER,
            PRIMARY KEY (document_id, page_id),
            FOREIGN KEY (document_id) REFERENCES documents (id),
            FOREIGN KEY (page_id) REFERENCES pages (id)
        );
        """
        )
        print("Table 'document_pages' created or already exists.")

        conn.commit()
        print("Database schema is up to date.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")


if __name__ == "__main__":
    print("Initializing database setup...")
    create_database()
    print("Database setup complete.")

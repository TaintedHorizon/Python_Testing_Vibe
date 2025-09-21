import sqlite3
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def upgrade_database():
    """
    Connects to the SQLite database and adds missing columns
    to existing tables without losing data.
    """
    db_path = os.getenv("DATABASE_PATH", "documents.db")
    if not os.path.exists(db_path):
        print(
            f"Database file not found at '{db_path}'. Please run database_setup.py first."
        )
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print(f"Successfully connected to database at '{db_path}'")

        # --- Helper function to safely add a column ---
        def add_column_if_not_exists(table_name, column_name, column_definition):
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [info[1] for info in cursor.fetchall()]
            if column_name not in columns:
                print(f"Adding column '{column_name}' to table '{table_name}'...")
                cursor.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                )
                print("  ... success.")
            else:
                print(
                    f"Column '{column_name}' already exists in table '{table_name}'. Skipping."
                )

        # --- Upgrade 'pages' table ---
        add_column_if_not_exists("pages", "status", "TEXT")
        add_column_if_not_exists("pages", "rotation_angle", "INTEGER DEFAULT 0")

        # --- Upgrade 'documents' table ---
        add_column_if_not_exists(
            "documents", "status", "TEXT NOT NULL DEFAULT 'pending_order'"
        )

        conn.commit()
        print("\nDatabase upgrade complete. All tables are up to date.")

    except sqlite3.Error as e:
        print(f"Database error during upgrade: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")


if __name__ == "__main__":
    print("Initializing database upgrade...")
    upgrade_database()

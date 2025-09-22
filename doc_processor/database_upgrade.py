# Standard library imports
import sqlite3
import os

# Third-party imports
from dotenv import load_dotenv

# Load environment variables from a .env file, such as the DATABASE_PATH.
load_dotenv()


def upgrade_database():
    """
    Connects to the SQLite database and safely adds any missing columns
    to existing tables. This allows for evolving the database schema over time
    without losing existing data. This script is idempotent, meaning it can be
    run multiple times without causing errors or changing the schema further
    if it's already up to date.
    """
    # Retrieve the database path from environment variables, with a default fallback.
    db_path = os.getenv("DATABASE_PATH", "documents.db")

    # Check if the database file exists before trying to connect and upgrade.
    if not os.path.exists(db_path):
        print(
            f"Database file not found at '{db_path}'. Please run database_setup.py first."
        )
        return

    try:
        # Establish the database connection.
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print(f"Successfully connected to database at '{db_path}'")

        # --- Helper function to safely add a column ---
        def add_column_if_not_exists(table_name, column_name, column_definition):
            """
            Checks if a column exists in a table and adds it if it does not.

            Args:
                table_name (str): The name of the table to check.
                column_name (str): The name of the column to add.
                column_definition (str): The SQL definition of the new column (e.g., 'TEXT NOT NULL DEFAULT \'pending\'').
            """
            # PRAGMA table_info returns a row for each column in the specified table.
            cursor.execute(f"PRAGMA table_info({table_name})")
            # Create a list of existing column names.
            columns = [info[1] for info in cursor.fetchall()]
            # Check if the desired column is already in the list.
            if column_name not in columns:
                print(f"Adding column '{column_name}' to table '{table_name}'...")
                # If the column does not exist, use ALTER TABLE to add it.
                cursor.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                )
                print("  ... success.")
            else:
                # If the column already exists, do nothing.
                print(
                    f"Column '{column_name}' already exists in table '{table_name}'. Skipping."
                )

        # --- Define Schema Upgrades ---
        # By calling the helper function, we can easily add new columns to tables
        # in future updates to the application.

        # Add 'status' and 'rotation_angle' to the 'pages' table.
        add_column_if_not_exists("pages", "status", "TEXT")
        add_column_if_not_exists("pages", "rotation_angle", "INTEGER DEFAULT 0")

        # Add 'status' to the 'documents' table.
        add_column_if_not_exists(
            "documents", "status", "TEXT NOT NULL DEFAULT 'pending_order'"
        )

        # Commit the changes to the database.
        conn.commit()
        print("\nDatabase upgrade complete. All tables are up to date.")

    except sqlite3.Error as e:
        # Handle potential database errors during the upgrade process.
        print(f"Database error during upgrade: {e}")
    finally:
        # Ensure the database connection is always closed.
        if conn:
            conn.close()
            print("Database connection closed.")


# --- Main Execution Block ---
if __name__ == "__main__":
    """
    This block is executed when the script is run directly.
    It serves as the entry point for initiating the database upgrade process.
    """
    print("Initializing database upgrade...")
    upgrade_database()
"""
This script manages the evolution of the database schema over time.
As an application develops, it's often necessary to add new columns to existing
tables to support new features. Directly altering a production database can be
risky and error-prone. This script provides a safe and controlled way to apply
these changes.

Key features of this script:
- **Idempotent**: It can be run many times without causing harm. It checks if a
  column already exists before trying to add it.
- **Non-destructive**: It only adds columns (`ALTER TABLE ... ADD COLUMN`). It
  never deletes tables or columns, preserving existing data.
- **Centralized**: All schema modifications are defined in one place, making it
  easy to track the history of database changes.

This script should be run after updating the application code to a new version
that requires database schema changes. It ensures the database is ready for the
new code to run correctly.
"""
# Standard library imports
import sqlite3
import os

# Third-party imports
from dotenv import load_dotenv

# Load environment variables from a .env file. This is used to get the
# DATABASE_PATH, ensuring the script connects to the correct database.
load_dotenv()


def upgrade_database():
    """
    Connects to the SQLite database and safely adds any missing columns
    to existing tables. This allows for evolving the database schema over time
    without losing existing data.
    """
    # Retrieve the database path from environment variables, with a default fallback.
    db_path = os.getenv("DATABASE_PATH", "documents.db")

    # A crucial check: if the database file doesn't exist, this script shouldn't
    # run. The database must be created first by `database_setup.py`.
    if not os.path.exists(db_path):
        print(
            f"Database file not found at '{db_path}'. Please run database_setup.py first."
        )
        return

    conn = None  # Initialize for the 'finally' block.
    try:
        # Establish the database connection.
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print(f"Successfully connected to database at '{db_path}' for upgrade.")

        # --- Helper function to safely add a column ---
        def add_column_if_not_exists(table_name, column_name, column_definition):
            """
            Checks if a column exists in a table and adds it if it does not.
            This is the core of the script's idempotency.

            Args:
                table_name (str): The name of the table to check.
                column_name (str): The name of the column to add.
                column_definition (str): The SQL definition for the new column
                                         (e.g., 'TEXT NOT NULL DEFAULT "pending"').
            """
            # `PRAGMA table_info(table_name)` is a SQLite command that returns
            # metadata about each column in the specified table.
            cursor.execute(f"PRAGMA table_info({table_name})")
            # We create a set of existing column names for efficient lookup.
            # The second item (index 1) in each returned row is the column name.
            existing_columns = {info[1] for info in cursor.fetchall()}

            # If the column is not in our set of existing columns, we can add it.
            if column_name not in existing_columns:
                print(f"Adding column '{column_name}' to table '{table_name}'...")
                # `ALTER TABLE` is the standard SQL command for modifying a table's structure.
                cursor.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                )
                print("  ... success.")
            else:
                # If the column already exists, we do nothing.
                print(
                    f"Column '{column_name}' already exists in table '{table_name}'. Skipping."
                )

        # --- Define Schema Upgrades ---
        # This section is the "migration log". When a new feature requires a
        # new column, a new call to `add_column_if_not_exists` is added here.
        # Over time, this section documents the evolution of the database schema.

        print("\nChecking for schema upgrades...")
        # Example: Add 'status' and 'rotation_angle' to the 'pages' table.
        # These might have been added in version 1.1 of the application.
        add_column_if_not_exists("pages", "status", "TEXT")
        add_column_if_not_exists("pages", "rotation_angle", "INTEGER DEFAULT 0")

        # Example: Add 'status' to the 'documents' table.
        # This might have been added in version 1.2.
        add_column_if_not_exists(
            "documents", "status", "TEXT NOT NULL DEFAULT 'pending_order'"
        )

        # Example: Add a column to store the final exported filename.
        # This might have been added in version 1.3.
        add_column_if_not_exists("documents", "final_filename_base", "TEXT")

        # Commit the changes to the database, making them permanent.
        conn.commit()
        print("\nDatabase upgrade check complete. Schema is up to date.")

    except sqlite3.Error as e:
        # Catch any SQLite-specific errors that occur during the process.
        print(f"Database error during upgrade: {e}")
    finally:
        # Ensure the database connection is always closed, even if errors occurred.
        if conn:
            conn.close()
            print("Database connection closed.")


# --- Main Execution Block ---
if __name__ == "__main__":
    """
    This block is executed only when the script is run directly from the command
    line (e.g., `python database_upgrade.py`). It serves as the entry point for
    initiating the database upgrade process.
    """
    print("Initializing database upgrade...")
    upgrade_database()

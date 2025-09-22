"""
This script, `database_upgrade.py`, is a critical utility for managing the evolution of the application's database schema.
In software development, as new features are added, it often becomes necessary to modify the database structure,
such as adding new columns to existing tables. Directly altering a production database can be risky and lead to data loss or inconsistencies.
This script provides a safe, controlled, and idempotent mechanism to apply these schema changes.

Key Design Principles and Features:
-   **Idempotency**: The script can be run multiple times without causing errors or unintended side effects.
    It achieves this by checking if a column already exists before attempting to add it.
-   **Non-destructive**: It is designed to only add columns (`ALTER TABLE ... ADD COLUMN`). It explicitly avoids
    operations that could lead to data loss, such as deleting tables, dropping columns, or modifying existing column types.
    This ensures that all existing data is preserved during the upgrade process.
-   **Centralized Migration Logic**: All database schema modifications are defined in one place within the `upgrade_database` function.
    This creates a clear, chronological record of how the database schema has evolved over time.

When to Run This Script:
This script should be executed whenever the application code is updated to a new version that introduces database schema changes.
It ensures that the database structure is compatible with the new code, allowing the application to run correctly.
It is typically run after `database_setup.py` (if setting up a new database) or after pulling new code changes in an existing environment.
"""
# Standard library imports
import sqlite3  # The Python standard library module for SQLite database interaction.
import os       # Used for interacting with the operating system, specifically to get environment variables.

# Third-party imports
from dotenv import load_dotenv  # Used to load environment variables from a .env file.

# Load environment variables from a .env file.
# This is crucial for configuring the `DATABASE_PATH`, ensuring the script connects to the correct database file.
load_dotenv()


def upgrade_database():
    """
    Connects to the SQLite database and safely adds any missing columns to existing tables.
    This function encapsulates the entire database schema upgrade logic.
    """
    # Retrieve the database path from environment variables.
    # A fallback to "documents.db" is provided if the environment variable is not set, though it's best practice to define it.
    db_path = os.getenv("DATABASE_PATH", "documents.db")

    # Critical Pre-check: Ensure the database file actually exists.
    # This script is for *upgrading* an existing database, not creating a new one.
    # If the file doesn't exist, it means `database_setup.py` hasn't been run yet.
    if not os.path.exists(db_path):
        print(
            f"[ERROR] Database file not found at '{db_path}'. Please run database_setup.py first to create the database."
        )
        return

    conn = None  # Initialize the connection variable to None for safe handling in the `finally` block.
    try:
        # Establish the database connection.
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print(f"Successfully connected to database at '{db_path}' for schema upgrade.")

        # --- Helper function to safely add a column if it doesn't already exist ---
        def add_column_if_not_exists(table_name, column_name, column_definition):
            """
            Checks if a specified column already exists in a given table.
            If the column does not exist, it executes an `ALTER TABLE ADD COLUMN` statement to add it.
            This function is the core of the script's idempotency and non-destructive nature.

            Args:
                table_name (str): The name of the table to inspect and potentially modify.
                column_name (str): The name of the column to check for and add.
                column_definition (str): The full SQL definition for the new column
                                         (e.g., 'TEXT NOT NULL DEFAULT "pending"').
            """
            # `PRAGMA table_info(table_name)` is a SQLite-specific command that returns
            # metadata about each column in the specified table. This is how we inspect the schema.
            cursor.execute(f"PRAGMA table_info({table_name})")
            # Extract all existing column names from the PRAGMA output for efficient lookup.
            # The column name is typically at index 1 of each returned row.
            existing_columns = {info[1] for info in cursor.fetchall()}

            # Conditional logic: Only add the column if it's not already present.
            if column_name not in existing_columns:
                print(f"Adding column '{column_name}' to table '{table_name}'...")
                # Execute the `ALTER TABLE ADD COLUMN` SQL statement.
                cursor.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                )
                print("  ... column added successfully.")
            else:
                # If the column already exists, simply log that it's being skipped.
                print(
                    f"Column '{column_name}' already exists in table '{table_name}'. Skipping addition."
                )

        # --- Define Schema Upgrades Here ---
        # This section acts as the "migration log" or "schema version control".
        # Each call to `add_column_if_not_exists` represents a specific schema change.
        # When a new feature requires a new column, a new call is added here.
        # The order of these calls is important if there are dependencies between column additions.

        print("\nChecking for necessary schema upgrades...")
        
        # Upgrade 1: Add 'status' and 'rotation_angle' to the 'pages' table.
        # These columns were likely introduced to track the processing status of each page
        # and its detected/corrected rotation angle.
        add_column_if_not_exists("pages", "status", "TEXT")
        add_column_if_not_exists("pages", "rotation_angle", "INTEGER DEFAULT 0")

        # Upgrade 2: Add 'status' to the 'documents' table.
        # This column allows tracking the workflow stage of a document (e.g., 'pending_order', 'order_set').
        add_column_if_not_exists(
            "documents", "status", "TEXT NOT NULL DEFAULT 'pending_order'"
        )

        # Upgrade 3: Add 'final_filename_base' to the 'documents' table.
        # This column stores the user-approved, filename-safe base name for the exported document.
        add_column_if_not_exists("documents", "final_filename_base", "TEXT")

        # Commit the changes to the database.
        # This makes all the `ALTER TABLE` operations permanent.
        conn.commit()
        print("\nDatabase upgrade check complete. Schema is up to date.")

    except sqlite3.Error as e:
        # Catch any SQLite-specific errors that might occur during the upgrade process.
        print(f"[CRITICAL ERROR] Database error during upgrade: {e}")
        # Note: `ALTER TABLE` statements in SQLite are often implicitly committed,
        # so a `conn.rollback()` here might not revert all changes depending on the exact error.
    finally:
        # Ensure the database connection is always closed, regardless of whether errors occurred.
        if conn:
            conn.close()
            print("Database connection closed.")


# --- Main Execution Block ---
if __name__ == "__main__":
    """
    This block ensures that the `upgrade_database()` function is called only when
    the script is executed directly from the command line (e.g., `python database_upgrade.py`).
    It serves as the entry point for initiating the database upgrade process.
    """
    print("Starting database upgrade process...")
    upgrade_database()
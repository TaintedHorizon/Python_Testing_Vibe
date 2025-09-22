"""
This module, `database.py`, serves as the dedicated Data Access Layer (DAL) for the entire application.
Its primary responsibility is to encapsulate all interactions with the SQLite database, providing a clean,
abstracted interface for other parts of the application (primarily `app.py` and `processing.py`).

Key Principles and Benefits:
-   **Separation of Concerns**: By centralizing all SQL queries and database logic here, the rest of the application
    can focus on business logic and presentation, without being cluttered by raw SQL statements.
-   **Maintainability**: If the database schema changes (e.g., a new column is added), only the functions within this
    module need to be updated, rather than searching through the entire codebase.
-   **Testability**: Database operations can be more easily mocked or tested in isolation.
-   **Readability**: Provides a higher-level, more semantic API (e.g., `get_pages_for_batch(batch_id)`) instead of
    requiring direct SQL knowledge in other modules.

Functions within this module are generally categorized into:
1.  **Data Retrieval (Queries)**: Functions that read data from the database using `SELECT` statements.
2.  **Data Modification (Commands)**: Functions that alter the database state using `INSERT`, `UPDATE`, or `DELETE` statements.
    These are typically wrapped in `with conn:` blocks to ensure atomic transactions (all or nothing).
"""
# Standard library imports
import sqlite3  # The Python standard library module for SQLite database interaction.
import os       # Used for interacting with the operating system, specifically to get environment variables.
from collections import defaultdict # A specialized dictionary subclass for grouping items.

# Third-party imports
from dotenv import load_dotenv  # Used to load environment variables from a .env file.

# Load environment variables from a .env file.
# This is crucial for configuring the `DATABASE_PATH` without hardcoding it directly into the source code.
load_dotenv()


# --- DATABASE CONNECTION UTILITY ---

def get_db_connection():
    """
    Establishes and configures a connection to the SQLite database.

    This function acts as a factory, creating and returning a new `sqlite3.Connection` object
    each time it is called. It retrieves the database file path from the `DATABASE_PATH`
    environment variable.

    Crucially, it sets the `row_factory` attribute of the connection to `sqlite3.Row`.
    This configuration allows database query results to be accessed like dictionaries
    (e.g., `row['column_name']`) instead of requiring access by numerical index (e.g., `row[0]`).
    This significantly improves code readability and reduces the likelihood of errors due to
    column order changes.

    Returns:
        sqlite3.Connection: A newly configured connection object to the SQLite database.
    """
    db_path = os.getenv("DATABASE_PATH")
    # Establish the connection to the SQLite database file.
    conn = sqlite3.connect(db_path)
    # Set the row_factory for dictionary-like access to query results.
    conn.row_factory = sqlite3.Row
    return conn


# --- DATA RETRIEVAL FUNCTIONS (QUERIES) ---
# These functions are designed to fetch data from the database without modifying it.

def get_pages_for_batch(batch_id):
    """
    Retrieves all individual pages associated with a specific batch ID.
    The results are ordered by their original filename and page number for consistent display.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        list: A list of `sqlite3.Row` objects, where each object represents a page.
              Returns an empty list if no pages are found for the given batch_id.
    """
    conn = get_db_connection()
    # Execute a SELECT query to fetch all columns (`*`) from the `pages` table
    # where the `batch_id` matches the provided argument.
    pages = conn.execute(
        "SELECT * FROM pages WHERE batch_id = ? ORDER BY source_filename, page_number",
        (batch_id,),
    ).fetchall()
    conn.close()
    return pages


def get_flagged_pages_for_batch(batch_id):
    """
    Retrieves all pages within a given batch that have been explicitly marked with a 'flagged' status.
    This is specifically used by the 'Review' screen in the UI, where users can address problematic pages.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        list: A list of `sqlite3.Row` objects, each representing a flagged page.
              The pages are ordered by their `id` for consistent retrieval.
    """
    conn = get_db_connection()
    pages = conn.execute(
        "SELECT * FROM pages WHERE batch_id = ? AND status = 'flagged' ORDER BY id",
        (batch_id,),
    ).fetchall()
    conn.close()
    return pages


def get_all_unique_categories():
    """
    Fetches a sorted list of all unique, non-empty categories that have been
    previously assigned to pages (either by AI or human verification).
    This function is crucial for populating category dropdowns in the UI,
    ensuring that users can select from a consistent and previously used set of categories.

    Returns:
        list: A sorted list of strings, where each string is a unique category name.
    """
    conn = get_db_connection()
    # `DISTINCT` ensures only unique category names are returned.
    # `WHERE human_verified_category IS NOT NULL AND human_verified_category != ''` filters out empty or unassigned categories.
    results = conn.execute(
        "SELECT DISTINCT human_verified_category FROM pages WHERE human_verified_category IS NOT NULL AND human_verified_category != '' ORDER BY human_verified_category"
    ).fetchall()
    conn.close()
    # Extract just the category name string from each `sqlite3.Row` object.
    return [row["human_verified_category"] for row in results]


def get_batch_by_id(batch_id):
    """
    Retrieves a single batch record from the `batches` table by its primary key.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        sqlite3.Row: A single row object representing the batch, or `None` if no batch with the given ID is found.
    """
    conn = get_db_connection()
    batch = conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
    conn.close()
    return batch


def count_flagged_pages_for_batch(batch_id):
    """
    Efficiently counts the number of pages marked as 'flagged' within a specific batch.
    This count is typically used for display on the Mission Control dashboard to alert the user to pending review tasks.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        int: The total count of flagged pages for the specified batch.
    """
    conn = get_db_connection()
    # Using `COUNT(*)` is significantly more efficient than fetching all rows and then calling `len()` on the result.
    count = conn.execute(
        "SELECT COUNT(*) FROM pages WHERE batch_id = ? AND status = 'flagged'",
        (batch_id,),
    ).fetchone()[0]
    conn.close()
    return count


def count_ungrouped_verified_pages(batch_id):
    """
    Counts the number of 'verified' pages in a batch that have not yet been assigned to any document.
    This count is crucial for determining if the 'grouping' step for a batch is complete.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        int: The total count of ungrouped, verified pages.
    """
    conn = get_db_connection()
    # This query uses a `LEFT JOIN` between `pages` and `document_pages`.
    # `dp.page_id IS NULL` condition identifies pages that exist in the `pages` table
    # but do not have a corresponding entry in the `document_pages` junction table,
    # meaning they are not yet part of any document.
    count = conn.execute(
        "SELECT COUNT(*) FROM pages p LEFT JOIN document_pages dp ON p.id = dp.page_id WHERE p.batch_id = ? AND p.status = 'verified' AND dp.page_id IS NULL",
        (batch_id,),
    ).fetchone()[0]
    conn.close()
    return count


def get_verified_pages_for_grouping(batch_id):
    """
    Retrieves all verified pages for a batch that are not yet part of a document,
    and groups them by their human-verified category.
    This is the primary data source for the 'Grouping' page in the UI.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        defaultdict: A dictionary where keys are category names (strings) and values are lists
                     of `sqlite3.Row` objects, each representing a page belonging to that category.
    """
    conn = get_db_connection()
    # Selects all columns from the `pages` table (`p.*`) for pages that are:
    # 1. Part of the specified `batch_id`.
    # 2. Have a `status` of 'verified'.
    # 3. Are not yet linked to any document (`dp.page_id IS NULL`).
    # Results are ordered for consistent display in the UI.
    pages = conn.execute(
        "SELECT p.* FROM pages p LEFT JOIN document_pages dp ON p.id = dp.page_id WHERE p.batch_id = ? AND p.status = 'verified' AND dp.page_id IS NULL ORDER BY p.human_verified_category, p.source_filename, p.page_number",
        (batch_id,),
    ).fetchall()
    conn.close()

    # `defaultdict(list)` is used here for convenient grouping.
    # When a category key is accessed for the first time, an empty list is automatically created for it.
    grouped_pages = defaultdict(list)
    for page in pages:
        grouped_pages[page["human_verified_category"]].append(page)
    return grouped_pages


def get_created_documents_for_batch(batch_id):
    """
    Retrieves all documents that have already been created for a specific batch.
    The documents are ordered by their creation time (newest first).
    This is used to display the list of existing documents on the 'Grouping' page.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        list: A list of `sqlite3.Row` objects, each representing a document.
    """
    conn = get_db_connection()
    documents = conn.execute(
        "SELECT * FROM documents WHERE batch_id = ? ORDER BY created_at DESC",
        (batch_id,),
    ).fetchall()
    conn.close()
    return documents


def get_documents_for_batch(batch_id):
    """
    Retrieves all documents for a batch and includes a calculated count of pages in each document.
    This function is used by the 'Ordering' and 'Finalize' pages in the UI.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        list: A list of `sqlite3.Row` objects. Each object represents a document
              and includes an additional `page_count` field.
    """
    conn = get_db_connection()
    # This complex query joins the `documents` table with the `document_pages` junction table.
    # It uses `GROUP BY d.id` and `COUNT(dp.page_id)` to count the number of pages associated with each document.
    # A `LEFT JOIN` is used to ensure that documents with zero pages (an edge case) are still included in the results.
    documents = conn.execute(
        """
        SELECT
            d.id, d.batch_id, d.document_name, d.status, d.created_at, d.final_filename_base,
            COUNT(dp.page_id) as page_count
        FROM documents d
        LEFT JOIN document_pages dp ON d.id = dp.document_id
        WHERE d.batch_id = ?
        GROUP BY d.id
        ORDER BY d.document_name
    """,
        (batch_id,),
    ).fetchall()
    conn.close()
    return documents


def get_pages_for_document(document_id):
    """
    Retrieves all pages linked to a specific document, ordered by their sequence number.
    This is essential for displaying pages in the correct order on the 'Ordering' page
    and for generating the final exported documents.

    Args:
        document_id (int): The unique identifier for the document.

    Returns:
        list: An ordered list of `sqlite3.Row` objects, each representing a page.
    """
    conn = get_db_connection()
    # This query joins the `pages` table with the `document_pages` junction table
    # to fetch the full details of each page belonging to the specified document.
    # The `ORDER BY dp.sequence ASC` clause ensures the pages are returned in their user-defined order.
    pages = conn.execute(
        """
        SELECT p.*, dp.sequence
        FROM pages p
        JOIN document_pages dp ON p.id = dp.page_id
        WHERE dp.document_id = ?
        ORDER BY dp.sequence ASC
    """,
        (document_id,),
    ).fetchall()
    conn.close()
    return pages


# --- DATA MODIFICATION FUNCTIONS (COMMANDS) ---
# These functions are responsible for changing the state of the database.

def update_page_data(page_id, category, status, rotation):
    """
    Updates the `human_verified_category`, `status`, and `rotation_angle` for a single page.
    This function is typically called after a user action on the 'Verify' or 'Review' screens.

    Args:
        page_id (int): The ID of the page to update.
        category (str): The new human-verified category for the page.
        status (str): The new status for the page (e.g., 'verified', 'flagged', 'pending_verification').
        rotation (int): The rotation angle (0, 90, 180, 270) to be stored for the page.
    """
    conn = get_db_connection()
    try:
        # Using the connection as a context manager (`with conn:`) automatically handles transactions.
        # If the code within the `with` block executes without error, changes are committed.
        # If an exception occurs, the transaction is automatically rolled back, ensuring data integrity.
        with conn:
            conn.execute(
                "UPDATE pages SET human_verified_category = ?, status = ?, rotation_angle = ? WHERE id = ?",
                (category, status, rotation, page_id),
            )
    except sqlite3.Error as e:
        print(f"Database error while updating page {page_id}: {e}")
    finally:
        if conn:
            conn.close()


def delete_page_by_id(page_id):
    """
    Deletes a page record from the database and also removes its corresponding
    image file from the filesystem to prevent orphaned files.

    Args:
        page_id (int): The ID of the page to delete.
    """
    conn = get_db_connection()
    try:
        with conn:
            # Step 1: Retrieve the path to the processed image file before deleting the database record.
            image_path_row = conn.execute(
                "SELECT processed_image_path FROM pages WHERE id = ?", (page_id,)
            ).fetchone()

            if image_path_row:
                image_path = image_path_row["processed_image_path"]
                
                # Step 2: Delete the page record from the `pages` table.
                # Due to the `ON DELETE CASCADE` foreign key constraint defined in `database_setup.py`
                # for the `document_pages` table, any entries linking this page to a document will be automatically removed.
                conn.execute("DELETE FROM pages WHERE id = ?", (page_id,))

                # Step 3: After successfully deleting the database record, remove the physical image file.
                if os.path.exists(image_path):
                    os.remove(image_path)
                    print(f"Deleted image file: {image_path}")
    except sqlite3.Error as e:
        print(f"Database error while deleting page {page_id}: {e}")
    finally:
        if conn:
            conn.close()


def create_document_and_link_pages(batch_id, document_name, page_ids):
    """
    Creates a new document record in the `documents` table and links a list of page IDs to it
    in the `document_pages` junction table. This is the core action of the 'Grouping' step.

    Args:
        batch_id (int): The ID of the batch this new document belongs to.
        document_name (str): The user-provided name for the new document.
        page_ids (list): A list of integer page IDs to be included in this document.
    """
    conn = get_db_connection()
    try:
        with conn:
            # Step 1: Insert the new document record and retrieve its auto-generated primary key (`doc_id`).
            cursor = conn.execute(
                "INSERT INTO documents (batch_id, document_name) VALUES (?, ?)",
                (batch_id, document_name),
            )
            doc_id = cursor.lastrowid

            # Step 2: Prepare the data for insertion into the `document_pages` junction table.
            # Each page is assigned a `sequence` number based on its order in the `page_ids` list.
            page_data = [(doc_id, pid, i + 1) for i, pid in enumerate(page_ids)]
            # `executemany` is an efficient way to insert multiple rows into the database in a single operation.
            conn.executemany(
                "INSERT INTO document_pages (document_id, page_id, sequence) VALUES (?, ?, ?)",
                page_data,
            )

            # Step 3: Quality-of-life update: If a document consists of only one page, its order is inherently set.
            # We can immediately mark its status as 'order_set' to skip the ordering step for single-page documents.
            if len(page_ids) == 1:
                conn.execute(
                    "UPDATE documents SET status = 'order_set' WHERE id = ?", (doc_id,)
                )
    except sqlite3.Error as e:
        print(f"Database error during document creation: {e}")
    finally:
        if conn:
            conn.close()


def reset_batch_grouping(batch_id):
    """
    Deletes all documents associated with a specific batch, effectively undoing the entire grouping step.
    The individual pages themselves are *not* deleted; they are simply returned to an 'ungrouped' state,
    making them available for re-grouping.

    Args:
        batch_id (int): The ID of the batch for which to reset grouping.
    """
    conn = get_db_connection()
    try:
        with conn:
            # Delete all document records belonging to the specified batch.
            # The `ON DELETE CASCADE` foreign key constraint on the `documents` table
            # will automatically handle the deletion of corresponding entries in the `document_pages` junction table.
            conn.execute("DELETE FROM documents WHERE batch_id = ?", (batch_id,))

            # Reset the batch status to 'verification_complete'. This allows the user
            # to re-enter the grouping step from the Mission Control dashboard.
            conn.execute(
                "UPDATE batches SET status = 'verification_complete' WHERE id = ?",
                (batch_id,),
            )
    except sqlite3.Error as e:
        print(f"Database error while resetting grouping for batch {batch_id}: {e}")
    finally:
        if conn:
            conn.close()


def update_page_sequence(document_id, page_ids_in_order):
    """
    Updates the sequence (order) of pages within a single document.
    This is called after the user has reordered pages using the drag-and-drop UI.

    Args:
        document_id (int): The ID of the document whose pages are being reordered.
        page_ids_in_order (list): A list of page IDs in their new desired order.
    """
    conn = get_db_connection()
    try:
        with conn:
            # Iterate through the provided list of page IDs. The index of each ID in the list
            # (plus one, as sequence numbers are 1-based) determines its new sequence number.
            for index, page_id in enumerate(page_ids_in_order):
                new_sequence_number = index + 1
                conn.execute(
                    "UPDATE document_pages SET sequence = ? WHERE document_id = ? AND page_id = ?",
                    (new_sequence_number, document_id, page_id),
                )
    except sqlite3.Error as e:
        print(
            f"Database error while updating page sequence for document {document_id}: {e}"
        )
    finally:
        if conn:
            conn.close()


def update_document_status(document_id, new_status):
    """
    Updates the `status` of a single document (e.g., to 'order_set', 'finalized').

    Args:
        document_id (int): The ID of the document to update.
        new_status (str): The new status string to set for the document.
    """
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE documents SET status = ? WHERE id = ?",
                (new_status, document_id),
            )
    except sqlite3.Error as e:
        print(f"Database error while updating status for document {document_id}: {e}")
    finally:
        if conn:
            conn.close()


def reset_batch_to_start(batch_id):
    """
    Completely resets a batch to its initial 'pending_verification' state.
    This is a **destructive** operation that undoes all grouping, ordering, and verification work
    for the specified batch.

    Args:
        batch_id (int): The ID of the batch to reset.
    """
    conn = get_db_connection()
    try:
        with conn:
            # Step 1: Delete all documents associated with the batch.
            # The `ON DELETE CASCADE` foreign key constraint on the `documents` table
            # ensures that corresponding entries in `document_pages` are also deleted.
            conn.execute("DELETE FROM documents WHERE batch_id = ?", (batch_id,))
            print(f"Deleted document groups for batch {batch_id}.")

            # Step 2: Reset the status, human-verified category, and rotation angle for all pages in the batch.
            # This effectively returns them to their initial state after OCR.
            conn.execute(
                """
                UPDATE pages
                SET status = 'pending_verification', human_verified_category = NULL, rotation_angle = 0
                WHERE batch_id = ?
            """,
                (batch_id,),
            )
            print(f"Reset page statuses and categories for batch {batch_id}.")

            # Step 3: Finally, reset the status of the batch itself.
            conn.execute(
                "UPDATE batches SET status = 'pending_verification' WHERE id = ?", (batch_id,)
            )
            print(f"Reset status for batch {batch_id}.")

    except sqlite3.Error as e:
        # The `with conn:` block ensures that if any of these steps fail,
        # all previous steps within this function are rolled back, maintaining database consistency.
        print(f"Database error while resetting batch {batch_id}. All changes rolled back. Error: {e}")
    finally:
        if conn:
            conn.close()


def update_document_final_filename(document_id, filename_base):
    """
    Saves the final, user-approved filename base for a document.
    This is typically called just before export and is used to reconstruct download links
    or for display in the 'View Exports' feature.

    Args:
        document_id (int): The ID of the document to update.
        filename_base (str): The final filename, without its extension (e.g., "My-Invoice-2023").
    """
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE documents SET final_filename_base = ? WHERE id = ?",
                (filename_base, document_id),
            )
    except sqlite3.Error as e:
        print(f"Database error while updating final filename for document {document_id}: {e}")
    finally:
        if conn:
            conn.close()

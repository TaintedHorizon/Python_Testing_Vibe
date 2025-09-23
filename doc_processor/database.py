# --- CATEGORY INSERTION HELPER ---
def insert_category_if_not_exists(category_name):
    """
    Inserts a new category into the categories table if it does not already exist (case-insensitive).
    Args:
        category_name (str): The name of the category to insert.
    """
    if not category_name:
        return
    conn = get_db_connection()
    try:
        with conn:
            # Use COLLATE NOCASE for case-insensitive uniqueness
            exists = conn.execute(
                "SELECT 1 FROM categories WHERE name = ? COLLATE NOCASE",
                (category_name,)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO categories (name) VALUES (?)",
                    (category_name,)
                )
    except sqlite3.Error as e:
        print(f"Database error while inserting category '{category_name}': {e}")
    finally:
        if conn:
            conn.close()
"""
This module serves as the Data Access Layer (DAL) for the application.
It encapsulates all the SQL queries and database interactions, providing a clean,
function-based API for the rest of the application (primarily `app.py`) to use.
This separation of concerns is crucial for maintainability, as it keeps raw SQL
out of the application logic and centralizes all database code in one place.

The functions are divided into two main categories:
1.  **Data Retrieval Functions (Queries)**: These functions read data from the
    database (using `SELECT` statements) and return it to the caller. They do
    not modify the state of the database.
2.  **Data Modification Functions (Commands)**: These functions change the data
    in the database (using `INSERT`, `UPDATE`, `DELETE` statements). They are
    wrapped in transactions to ensure atomicity.

Using a dedicated module like this makes the code easier to test, debug, and
refactor. For example, if the database schema changes, only the functions in
this file need to be updated.
"""
# Standard library imports
import sqlite3
import os
from collections import defaultdict

# Third-party imports
from dotenv import load_dotenv

# Load environment variables from a .env file, particularly for the DATABASE_PATH.
load_dotenv()


# --- DATABASE CONNECTION UTILITY ---

def get_db_connection():
    """
    Establishes and configures a connection to the SQLite database.

    This is a factory function that creates a new database connection each time
    it's called. It retrieves the database file path from the environment
    variables. Crucially, it sets the `row_factory` to `sqlite3.Row`, which
    allows accessing query results like dictionaries (e.g., `row['column_name']`)
    instead of just by index. This makes the code much more readable and less
    prone to errors.

    Returns:
        sqlite3.Connection: A configured connection object to the database.
    """
    db_path = os.getenv("DATABASE_PATH")
    conn = sqlite3.connect(db_path)
    # This factory is a game-changer for readability. Instead of row[0], row[1],
    # we can use row['id'], row['status'], etc.
    conn.row_factory = sqlite3.Row
    return conn


# --- DATA RETRIEVAL FUNCTIONS (QUERIES) ---
# These functions are responsible for reading information from the database.

def get_pages_for_batch(batch_id):
    """
    Retrieves all pages associated with a specific batch ID, sorted for
    consistent display.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        list: A list of sqlite3.Row objects, where each object represents a page.
              Returns an empty list if no pages are found.
    """
    conn = get_db_connection()
    pages = conn.execute(
        "SELECT * FROM pages WHERE batch_id = ? ORDER BY source_filename, page_number",
        (batch_id,),
    ).fetchall()
    conn.close()
    return pages


def get_flagged_pages_for_batch(batch_id):
    """
    Retrieves all pages that have been marked with a 'flagged' status for a
    given batch. This is used by the 'Review' screen.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        list: A list of sqlite3.Row objects for the flagged pages.
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
    previously verified by a human user. This is used to populate the category
    dropdowns in the UI, ensuring consistency.

    Returns:
        list: A sorted list of strings, where each string is a unique category name.
    """
    conn = get_db_connection()
    results = conn.execute(
        "SELECT DISTINCT human_verified_category FROM pages WHERE human_verified_category IS NOT NULL AND human_verified_category != '' ORDER BY human_verified_category"
    ).fetchall()
    conn.close()
    # The query returns a list of Row objects; this list comprehension extracts
    # just the category name string from each row.
    return [row["human_verified_category"] for row in results]


def get_batch_by_id(batch_id):
    """
    Retrieves a single batch record by its primary key.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        sqlite3.Row: A single row object representing the batch, or None if not found.
    """
    conn = get_db_connection()
    batch = conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
    conn.close()
    return batch


def count_flagged_pages_for_batch(batch_id):
    """
    Efficiently counts the number of pages marked as 'flagged' within a batch.
    Used for display on the Mission Control dashboard.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        int: The total count of flagged pages.
    """
    conn = get_db_connection()
    # Using COUNT(*) is much more efficient than fetching all rows and using len().
    count = conn.execute(
        "SELECT COUNT(*) FROM pages WHERE batch_id = ? AND status = 'flagged'",
        (batch_id,),
    ).fetchone()[0]
    conn.close()
    return count


def count_ungrouped_verified_pages(batch_id):
    """
    Counts 'verified' pages in a batch that have not yet been assigned to a document.
    This is key for determining if the 'grouping' step is complete.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        int: The total count of ungrouped, verified pages.
    """
    conn = get_db_connection()
    # This query is a bit more complex. It uses a LEFT JOIN to link `pages`
    # with `document_pages`. If a page has no match in `document_pages`
    # (i.e., `dp.page_id IS NULL`), it means it hasn't been assigned to a document.
    count = conn.execute(
        "SELECT COUNT(*) FROM pages p LEFT JOIN document_pages dp ON p.id = dp.page_id WHERE p.batch_id = ? AND p.status = 'verified' AND dp.page_id IS NULL",
        (batch_id,),
    ).fetchone()[0]
    conn.close()
    return count


def get_verified_pages_for_grouping(batch_id):
    """
    Retrieves all verified pages for a batch that are not yet part of a document,
    and groups them by their human-verified category. This is the primary data
    source for the 'Grouping' page.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        defaultdict: A dictionary where keys are category names and values are lists
                     of page row objects belonging to that category.
    """
    conn = get_db_connection()
    # This query selects all columns from the pages table (`p.*`) for pages that
    # meet the criteria of being 'verified' and not yet grouped.
    pages = conn.execute(
        "SELECT p.* FROM pages p LEFT JOIN document_pages dp ON p.id = dp.page_id WHERE p.batch_id = ? AND p.status = 'verified' AND dp.page_id IS NULL ORDER BY p.human_verified_category, p.source_filename, p.page_number",
        (batch_id,),
    ).fetchall()
    conn.close()

    # `defaultdict(list)` is a convenient way to group items. When we access a
    # key for the first time, it automatically creates an empty list for that key,
    # avoiding the need for `if key not in dict:` checks.
    grouped_pages = defaultdict(list)
    for page in pages:
        grouped_pages[page["human_verified_category"]].append(page)
    return grouped_pages


def get_created_documents_for_batch(batch_id):
    """
    Retrieves all documents that have already been created for a specific batch,
    ordered by creation time. Used to display the list of existing documents on
    the 'Grouping' page.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        list: A list of sqlite3.Row objects, each representing a document.
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
    Retrieves all documents for a batch and includes a count of pages in each one.
    This is used for the 'Ordering' and 'Finalize' pages.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        list: A list of sqlite3.Row objects, where each object represents a
              document and includes a 'page_count' field.
    """
    conn = get_db_connection()
    # This query joins `documents` with `document_pages` and uses `GROUP BY`
    # and `COUNT` to calculate how many pages are linked to each document.
    # A LEFT JOIN is used to ensure that documents with zero pages (an edge case)
    # would still be included in the results.
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
    Retrieves all pages linked to a specific document, correctly ordered by their
    sequence number. This is essential for the 'Ordering' and 'Export' features.

    Args:
        document_id (int): The unique identifier for the document.

    Returns:
        list: An ordered list of sqlite3.Row objects, each representing a page.
    """
    conn = get_db_connection()
    # This query joins `pages` and `document_pages` to fetch the full details
    # of each page belonging to the specified document, sorted by the `sequence`
    # number stored in the junction table.
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


def get_all_categories():
    """
    Fetches all category names from the dedicated 'categories' table.

    Returns:
        list: A sorted list of strings, where each string is a category name.
    """
    conn = get_db_connection()
    # The query returns a list of Row objects; this list comprehension extracts
    # just the category name string from each row.
    categories = conn.execute("SELECT name FROM categories ORDER BY name ASC").fetchall()
    conn.close()
    return [row["name"] for row in categories]


# --- DATA MODIFICATION FUNCTIONS (COMMANDS) ---
# These functions change the state of the database.

def update_page_data(page_id, category, status, rotation):
    """
    Updates the data for a single page, typically after a user action on the
    'Verify' or 'Review' screen.

    Args:
        page_id (int): The ID of the page to update.
        category (str): The new human-verified category.
        status (str): The new status (e.g., 'verified', 'flagged').
        rotation (int): The rotation angle to save (0, 90, 180, 270).
    """
    conn = get_db_connection()
    try:
        # Using the connection as a context manager (`with conn:`) automatically
        # handles transactions. The changes are only committed if the block
        # executes successfully. If an error occurs, the transaction is
        # automatically rolled back.
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
    Deletes a page from the database and also removes its corresponding
    image file from the filesystem to prevent orphaned files.

    Args:
        page_id (int): The ID of the page to delete.
    """
    conn = get_db_connection()
    try:
        with conn:
            # First, we need to find the path to the image file before we delete
            # the database record.
            image_path_row = conn.execute(
                "SELECT processed_image_path FROM pages WHERE id = ?", (page_id,)
            ).fetchone()

            if image_path_row:
                image_path = image_path_row["processed_image_path"]
                # Delete the database record. Because of `ON DELETE CASCADE` in the
                # `document_pages` table, any links to this page will be auto-removed.
                conn.execute("DELETE FROM pages WHERE id = ?", (page_id,))

                # After successfully deleting the DB record, delete the file.
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
    Creates a new document record and links a list of page IDs to it. This
    is the core action of the 'Grouping' step.

    Args:
        batch_id (int): The ID of the batch this document belongs to.
        document_name (str): The name for the new document.
        page_ids (list): A list of integer page IDs to include in the document.
    """
    conn = get_db_connection()
    try:
        with conn:
            # First, create the new document record and get its newly generated ID.
            cursor = conn.execute(
                "INSERT INTO documents (batch_id, document_name) VALUES (?, ?)",
                (batch_id, document_name),
            )
            doc_id = cursor.lastrowid

            # Prepare data for the junction table. We assign a sequence number
            # based on the order of IDs in the input list.
            page_data = [(doc_id, pid, i + 1) for i, pid in enumerate(page_ids)]
            # `executemany` is an efficient way to insert multiple rows at once.
            conn.executemany(
                "INSERT INTO document_pages (document_id, page_id, sequence) VALUES (?, ?, ?)",
                page_data,
            )

            # A quality-of-life update: if the document has only one page, its
            # order is already final, so we can mark it as 'order_set'.
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
    Deletes all documents associated with a batch, effectively undoing the
    entire grouping step for that batch. The pages themselves are not deleted,
    but are returned to an 'ungrouped' state.

    Args:
        batch_id (int): The ID of the batch to reset.
    """
    conn = get_db_connection()
    try:
        with conn:
            # We don't need to manually delete from `document_pages` because the
            # `ON DELETE CASCADE` constraint on the `documents` foreign key
            # handles it automatically. Deleting a document will cascade to
            # delete its entries in `document_pages`.
            conn.execute("DELETE FROM documents WHERE batch_id = ?", (batch_id,))

            # Reset the batch status so the user can re-enter the grouping step.
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

    Args:
        document_id (int): The ID of the document to update.
        page_ids_in_order (list): A list of page IDs in their new desired order.
    """
    conn = get_db_connection()
    try:
        with conn:
            # Iterate through the provided list of page IDs. The index of each
            # ID in the list determines its new sequence number.
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
    Updates the status of a single document (e.g., to 'order_set').

    Args:
        document_id (int): The ID of the document to update.
        new_status (str): The new status string.
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
    This is a destructive operation that undoes all grouping and verification work.

    Args:
        batch_id (int): The ID of the batch to reset.
    """
    conn = get_db_connection()
    try:
        with conn:
            # Delete all documents associated with the batch. The `ON DELETE CASCADE`
            # will handle cleaning up the `document_pages` entries.
            conn.execute("DELETE FROM documents WHERE batch_id = ?", (batch_id,))
            print(f"Deleted document groups for batch {batch_id}.")

            # Reset the status, category, and rotation for all pages in the batch.
            conn.execute(
                """
                UPDATE pages
                SET status = 'pending_verification', human_verified_category = NULL, rotation_angle = 0
                WHERE batch_id = ?
            """,
                (batch_id,),
            )
            print(f"Reset page statuses and categories for batch {batch_id}.")

            # Finally, reset the status of the batch itself.
            conn.execute(
                "UPDATE batches SET status = 'pending_verification' WHERE id = ?", (batch_id,)
            )
            print(f"Reset status for batch {batch_id}.")

    except sqlite3.Error as e:
        # The `with conn:` block ensures that if any of these steps fail,
        # all previous steps in this function are rolled back.
        print(f"Database error while resetting batch {batch_id}. All changes rolled back. Error: {e}")
    finally:
        if conn:
            conn.close()


def update_document_final_filename(document_id, filename_base):
    """
    Saves the final, user-approved filename base for a document right before export.
    This is used to reconstruct download links in the 'View Exports' feature.

    Args:
        document_id (int): The ID of the document to update.
        filename_base (str): The final filename, without its extension.
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
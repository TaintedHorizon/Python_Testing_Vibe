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
    Establishes a connection to the SQLite database.

    This function retrieves the database path from the environment variables.
    It configures the connection to return rows that behave like dictionaries
    (via sqlite3.Row), which allows accessing columns by name.

    Returns:
        sqlite3.Connection: A connection object to the database.
    """
    db_path = os.getenv("DATABASE_PATH")
    conn = sqlite3.connect(db_path)
    # This factory allows accessing query results by column name, like a dictionary.
    conn.row_factory = sqlite3.Row
    return conn


# --- DATA RETRIEVAL FUNCTIONS (QUERIES) ---

def get_pages_for_batch(batch_id):
    """
    Retrieves all pages associated with a specific batch ID.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        list: A list of sqlite3.Row objects, where each row is a page.
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
    Retrieves all pages that have been marked with a 'flagged' status for a given batch.

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
    verified by a human user.

    Returns:
        list: A list of strings, where each string is a unique category name.
    """
    conn = get_db_connection()
    results = conn.execute(
        "SELECT DISTINCT human_verified_category FROM pages WHERE human_verified_category IS NOT NULL AND human_verified_category != '' ORDER BY human_verified_category"
    ).fetchall()
    conn.close()
    # Extract the category name from each row object.
    return [row["human_verified_category"] for row in results]


def get_batch_by_id(batch_id):
    """
    Retrieves a single batch record by its ID.

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
    Counts the number of pages marked as 'flagged' within a specific batch.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        int: The total count of flagged pages.
    """
    conn = get_db_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM pages WHERE batch_id = ? AND status = 'flagged'",
        (batch_id,),
    ).fetchone()[0]
    conn.close()
    return count


def count_ungrouped_verified_pages(batch_id):
    """
    Counts the number of 'verified' pages in a batch that have not yet been
    assigned to a document.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        int: The total count of ungrouped, verified pages.
    """
    conn = get_db_connection()
    # This query uses a LEFT JOIN to find pages that do not have a corresponding
    # entry in the document_pages junction table.
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

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        defaultdict: A dictionary where keys are category names and values are lists
                     of page row objects belonging to that category.
    """
    conn = get_db_connection()
    # Similar to the count function, this uses a LEFT JOIN to find ungrouped pages.
    pages = conn.execute(
        "SELECT p.* FROM pages p LEFT JOIN document_pages dp ON p.id = dp.page_id WHERE p.batch_id = ? AND p.status = 'verified' AND dp.page_id IS NULL ORDER BY p.human_verified_category, p.source_filename, p.page_number",
        (batch_id,),
    ).fetchall()
    conn.close()
    # Use defaultdict to easily group pages by category.
    grouped_pages = defaultdict(list)
    for page in pages:
        grouped_pages[page["human_verified_category"]].append(page)
    return grouped_pages


def get_created_documents_for_batch(batch_id):
    """
    Retrieves all documents that have been created for a specific batch.

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
    Retrieves all documents for a batch, including a count of pages in each.

    Args:
        batch_id (int): The unique identifier for the batch.

    Returns:
        list: A list of sqlite3.Row objects, each representing a document
              and including a 'page_count' field.
    """
    conn = get_db_connection()
    # This query joins documents with the document_pages table and groups by document
    # to get a count of pages for each document.
    documents = conn.execute(
        """
        SELECT
            d.id, d.batch_id, d.document_name, d.status, d.created_at,
            COUNT(dp.page_id) as page_count
        FROM documents d
        JOIN document_pages dp ON d.id = dp.document_id
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
    Retrieves all pages linked to a specific document, ordered by their sequence.

    Args:
        document_id (int): The unique identifier for the document.

    Returns:
        list: A list of sqlite3.Row objects, each representing a page in the document.
    """
    conn = get_db_connection()
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

def update_page_data(page_id, category, status, rotation):
    """
    Updates the data for a single page after user verification.

    Args:
        page_id (int): The ID of the page to update.
        category (str): The new human-verified category.
        status (str): The new status (e.g., 'verified', 'flagged').
        rotation (int): The rotation angle to save.
    """
    conn = get_db_connection()
    try:
        # Use a 'with' statement for transaction management (commit/rollback).
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
    Deletes a page from the database and its corresponding image file from disk.

    Args:
        page_id (int): The ID of the page to delete.
    """
    conn = get_db_connection()
    try:
        with conn:
            # First, retrieve the path of the image file to be deleted.
            image_path_row = conn.execute(
                "SELECT processed_image_path FROM pages WHERE id = ?", (page_id,)
            ).fetchone()

            if image_path_row:
                image_path = image_path_row["processed_image_path"]
                # Delete the database record.
                conn.execute("DELETE FROM pages WHERE id = ?", (page_id,))
                # If the image file exists, delete it from the filesystem.
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
    Creates a new document record and links a list of page IDs to it.

    Args:
        batch_id (int): The ID of the batch this document belongs to.
        document_name (str): The name for the new document.
        page_ids (list): A list of page IDs to include in the document.
    """
    conn = get_db_connection()
    try:
        with conn:
            # Create the new document record and get its ID.
            doc_id = conn.execute(
                "INSERT INTO documents (batch_id, document_name) VALUES (?, ?)",
                (batch_id, document_name),
            ).lastrowid

            # Create the links in the junction table.
            page_data = [(doc_id, pid, i + 1) for i, pid in enumerate(page_ids)]
            conn.executemany(
                "INSERT INTO document_pages (document_id, page_id, sequence) VALUES (?, ?, ?)",
                page_data,
            )

            # If the created document has only one page, its order is implicitly set.
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
    Deletes all documents associated with a batch, effectively undoing the grouping step.
    The pages themselves are not deleted.

    Args:
        batch_id (int): The ID of the batch to reset.
    """
    conn = get_db_connection()
    try:
        with conn:
            # Find all documents in the batch.
            docs_to_delete = conn.execute(
                "SELECT id FROM documents WHERE batch_id = ?", (batch_id,)
            ).fetchall()

            if docs_to_delete:
                doc_ids = [doc["id"] for doc in docs_to_delete]
                # Delete all links from pages to these documents.
                # Note: Using f-string for IN clause is safe here because doc_ids are integers from the DB.
                placeholders = ",".join(["?"] * len(doc_ids))
                conn.execute(
                    f"DELETE FROM document_pages WHERE document_id IN ({placeholders})",
                    doc_ids,
                )
                # Delete the documents themselves.
                conn.execute("DELETE FROM documents WHERE batch_id = ?", (batch_id,))

            # Reset the batch status to allow re-grouping.
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
    Updates the sequence (order) of pages within a document.

    Args:
        document_id (int): The ID of the document to update.
        page_ids_in_order (list): A list of page IDs in their new desired order.
    """
    conn = get_db_connection()
    try:
        with conn:
            # Iterate through the list and update the sequence number for each page.
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
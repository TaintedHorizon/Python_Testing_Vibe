# --- INTERACTION LOGGING UTILITIES ---
def log_interaction(batch_id, document_id=None, user_id=None, event_type=None, step=None, content=None, notes=None):
    """
    Inserts a new interaction log entry into the interaction_log table.
    Args:
        batch_id (int): The batch this event is associated with.
        document_id (int, optional): The document this event is associated with.
        user_id (str, optional): The user performing the action.
        event_type (str): The type of event ('ai_prompt', 'ai_response', 'human_correction', 'status_change', etc.).
        step (str, optional): The workflow step ('verify', 'review', 'group', 'order', 'name', etc.).
        content (str, optional): The prompt, response, correction, or status info (JSON or text).
        notes (str, optional): Any extra context.
    """
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO interaction_log (batch_id, document_id, user_id, event_type, step, content, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (batch_id, document_id, user_id, event_type, step, content, notes)
            )
    except sqlite3.Error as e:
        print(f"Database error while logging interaction: {e}")
    finally:
        if conn:
            conn.close()

def get_interactions_for_document(document_id):
    """
    Retrieves all interaction log entries for a given document, ordered by timestamp.
    Args:
        document_id (int): The document to fetch logs for.
    Returns:
        list: A list of sqlite3.Row objects for each log entry.
    """
    conn = get_db_connection()
    try:
        logs = conn.execute(
            "SELECT * FROM interaction_log WHERE document_id = ? ORDER BY timestamp ASC",
            (document_id,)
        ).fetchall()
        return logs
    except sqlite3.Error as e:
        print(f"Database error while fetching interaction logs for document {document_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_interactions_for_batch(batch_id):
    """
    Retrieves all interaction log entries for a given batch, ordered by timestamp.
    Args:
        batch_id (int): The batch to fetch logs for.
    Returns:
        list: A list of sqlite3.Row objects for each log entry.
    """
    conn = get_db_connection()
    try:
        logs = conn.execute(
            "SELECT * FROM interaction_log WHERE batch_id = ? ORDER BY timestamp ASC",
            (batch_id,)
        ).fetchall()
        return logs
    except sqlite3.Error as e:
        print(f"Database error while fetching interaction logs for batch {batch_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()
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
                try:
                    invalidate_category_cache()
                except Exception:
                    pass
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
import json
import stat
import time
from collections import defaultdict
import logging

# Third-party imports
from dotenv import load_dotenv

# Load environment variables from a .env file, particularly for the DATABASE_PATH.
load_dotenv()


# --- DATABASE CONNECTION UTILITY ---

def _gather_db_file_metadata(db_path: str) -> dict:
    """Return metadata about the SQLite database file for richer startup logging."""
    info = {
        "path": os.path.abspath(db_path),
        "exists": False,
    }
    try:
        if os.path.exists(db_path):
            st = os.stat(db_path)
            info.update(
                {
                    "exists": True,
                    "size_bytes": st.st_size,
                    "last_modified_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime)),
                    "permissions_octal": oct(stat.S_IMODE(st.st_mode)),
                }
            )
    except Exception as e:
        info["metadata_error"] = str(e)
    return info


_DB_LOGGED_ONCE = False

# --- CATEGORY CACHE (active categories) ---
_CATEGORY_CACHE = { 'data': None, 'loaded_at': 0 }
_CATEGORY_CACHE_TTL = 60  # seconds

def invalidate_category_cache():
    _CATEGORY_CACHE['data'] = None
    _CATEGORY_CACHE['loaded_at'] = 0


def get_db_connection():
    """Create and return a configured SQLite connection (logs rich context once).

    Prefers the centralized config_manager.AppConfig.DATABASE_PATH. Falls back to
    the DATABASE_PATH environment variable for backward compatibility.
    """
    global _DB_LOGGED_ONCE
    try:
        # Prefer centralized config first
        from .config_manager import app_config  # local import to avoid cycles
        db_path = app_config.DATABASE_PATH
        # Test fixtures may override DATABASE_PATH via environment AFTER config_manager loaded.
        # Honor an explicit env var if it points to a different location (exists or parent dir writable).
        env_override = os.getenv("DATABASE_PATH")
        if env_override and os.path.abspath(env_override) != os.path.abspath(db_path):
            try:
                override_dir = os.path.dirname(env_override)
                if not override_dir:
                    override_dir = '.'
                os.makedirs(override_dir, exist_ok=True)
                db_path = env_override  # switch to override for this connection
            except Exception as _ovr_err:
                logging.getLogger(__name__).warning(f"Ignored DATABASE_PATH override {env_override}: {_ovr_err}")
    except Exception:
        # Fallback purely to environment
        db_path = os.getenv("DATABASE_PATH")
    if not db_path:
        raise RuntimeError("Database path is not configured. Set in .env or via config_manager.")

    if not _DB_LOGGED_ONCE:
        # Structured, one-time metadata log (safe even if logger not configured yet)
        meta = _gather_db_file_metadata(db_path)
        payload = {
            "event": "database_init",
            "description": "SQLite database configuration",
            "metadata": meta,
        }
        try:
            logging.getLogger(__name__).info(json.dumps(payload))
        except Exception:
            # Fallback minimal print if logging not yet configured
            print(f"[APP][database_init] {payload}")
        _DB_LOGGED_ONCE = True

    conn = sqlite3.connect(db_path, timeout=30.0)  # 30 second timeout for locks
    conn.row_factory = sqlite3.Row
    
    # Enable WAL mode for better concurrent access
    conn.execute("PRAGMA journal_mode=WAL")
    
    # Set busy timeout for additional safety
    conn.execute("PRAGMA busy_timeout=30000")  # 30 seconds in milliseconds
    
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

def get_active_categories():
    """Return list of active category names with simple cache.

    On failure fall back to historical distinct categories (not cached) to avoid
    masking structural issues. Cache TTL configurable via _CATEGORY_CACHE_TTL.
    """
    import time as _time
    now = _time.time()
    if _CATEGORY_CACHE['data'] is not None and (now - _CATEGORY_CACHE['loaded_at'] < _CATEGORY_CACHE_TTL):
        return _CATEGORY_CACHE['data']
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT name FROM categories WHERE is_active = 1 ORDER BY name COLLATE NOCASE").fetchall()
        data = [r["name"] for r in rows]
        _CATEGORY_CACHE['data'] = data
        _CATEGORY_CACHE['loaded_at'] = now
        conn.close()
        return data
    except Exception:
        conn.close()
        return get_all_unique_categories()


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
    Used for display on the Batch Control dashboard.

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
    print(f"[DEBUG] count_ungrouped_verified_pages for batch {batch_id}: {count}")
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

def get_single_documents_for_batch(batch_id):
    """Return single-document workflow records for a batch.

    NOTE: Intentionally excludes recently added optional columns (final_category,
    final_filename) so tests with minimal schemas (without migration) still pass.
    Route layer hydrates those if present.
    """
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, original_filename, original_pdf_path,
                   ai_suggested_category, ai_suggested_filename,
                   ai_confidence, ai_summary, ocr_text, ocr_confidence_avg
            FROM single_documents
            WHERE batch_id = ?
            ORDER BY id
            """,
            (batch_id,)
        ).fetchall()
        return rows
    except sqlite3.Error as e:
        print(f"Database error while fetching single_documents for batch {batch_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()


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

def update_page_rotation(page_id: int, rotation: int) -> bool:
    """Update only the rotation_angle for a page.

    Args:
        page_id (int): Page primary key.
        rotation (int): One of 0,90,180,270.

    Returns:
        bool: True on success, False on error or invalid rotation.
    """
    if rotation not in {0,90,180,270}:
        return False
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("UPDATE pages SET rotation_angle = ? WHERE id = ?", (rotation, page_id))
        return True
    except Exception as e:
        print(f"Database error while updating rotation for page {page_id}: {e}")
        return False
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

            # Explicitly delete all document_pages for this batch, including orphans
            print(f"[RESET GROUPING] Deleting all document_pages for batch {batch_id} (including orphans)")
            conn.execute("""
                DELETE FROM document_pages
                WHERE document_id IN (SELECT id FROM documents WHERE batch_id = ?)
                   OR page_id IN (SELECT id FROM pages WHERE batch_id = ?)
            """, (batch_id, batch_id))
            print(f"[RESET GROUPING] Deleted all document_pages for batch {batch_id}.")

            # Now delete all documents for the batch
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
    print(f"[DB] reset_batch_to_start called for batch_id={batch_id}")
    conn = get_db_connection()
    try:
        with conn:

            # Delete all document_pages for this batch, even if documents are already gone (orphan cleanup)
            print(f"[DB] Deleting all document_pages for batch {batch_id} (including orphans)")
            conn.execute("""
                DELETE FROM document_pages
                WHERE document_id IN (SELECT id FROM documents WHERE batch_id = ?)
                   OR page_id IN (SELECT id FROM pages WHERE batch_id = ?)
            """, (batch_id, batch_id))
            print(f"[DB] Deleted all document_pages for batch {batch_id}.")

            # Delete all documents associated with the batch (grouping info)
            print(f"[DB] Deleting documents for batch {batch_id}")
            conn.execute("DELETE FROM documents WHERE batch_id = ?", (batch_id,))
            print(f"[DB] Deleted document groups for batch {batch_id}.")

            # Reset the status, category, and rotation for all pages in the batch.
            print(f"[DB] Resetting page statuses and categories for batch {batch_id}")
            cur = conn.execute(
                """
                UPDATE pages
                SET status = 'pending_verification', human_verified_category = NULL, rotation_angle = 0
                WHERE batch_id = ?
            """,
                (batch_id,),
            )
            print(f"[DB] Reset page statuses and categories for batch {batch_id}. Rows updated: {cur.rowcount}")
            conn.commit()

            # Finally, reset the status of the batch itself.
            print(f"[DB] Resetting batch status for batch {batch_id}")
            conn.execute(
                "UPDATE batches SET status = 'pending_verification' WHERE id = ?", (batch_id,)
            )
            print(f"[DB] Reset status for batch {batch_id}.")

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

def log_detection_ground_truth(filename, predicted_strategy, actual_strategy, confidence, user_feedback=None):
    """
    Log ground truth data when user corrects or validates detection decisions.
    This creates training data for improving LLM detection accuracy.
    
    Args:
        filename (str): Name of the file that was classified
        predicted_strategy (str): What the system predicted ('single_document' or 'batch_scan') 
        actual_strategy (str): What it actually was according to user
        confidence (float): System's confidence in the prediction (0.0 to 1.0)
        user_feedback (str, optional): User's comments about the decision
    """
    try:
        ground_truth_data = {
            "filename": filename,
            "predicted_strategy": predicted_strategy,
            "actual_strategy": actual_strategy,
            "confidence": confidence,
            "correct_prediction": predicted_strategy == actual_strategy,
            "user_feedback": user_feedback
        }
        
        log_interaction(
            batch_id=None,
            document_id=None,
            user_id="system",  # Use system since get_current_user_id not available here
            event_type="detection_ground_truth",
            step="user_validation", 
            content=str(ground_truth_data),
            notes=f"Ground truth: {actual_strategy} (predicted: {predicted_strategy}, correct: {predicted_strategy == actual_strategy})"
        )
    except Exception as e:
        print(f"Error logging ground truth data: {e}")

def get_detection_training_data(limit=100):
    """
    Retrieve recent detection decisions and ground truth data for LLM training.
    
    Args:
        limit (int): Maximum number of records to return
        
    Returns:
        dict: Training data with detection decisions and ground truth validations
    """
    conn = get_db_connection()
    try:
        # Get recent detection decisions
        detection_decisions = conn.execute(
            """
            SELECT * FROM interaction_log 
            WHERE event_type IN ('document_detection_decision', 'llm_detection_analysis') 
            ORDER BY timestamp DESC 
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
        
        # Get ground truth validations
        ground_truth = conn.execute(
            """
            SELECT * FROM interaction_log 
            WHERE event_type = 'detection_ground_truth' 
            ORDER BY timestamp DESC 
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
        
        return {
            "detection_decisions": [dict(row) for row in detection_decisions],
            "ground_truth": [dict(row) for row in ground_truth],
            "total_decisions": len(detection_decisions),
            "total_validations": len(ground_truth)
        }
        
    except sqlite3.Error as e:
        print(f"Database error while fetching training data: {e}")
        return {"detection_decisions": [], "ground_truth": [], "total_decisions": 0, "total_validations": 0}
    finally:
        if conn:
            conn.close()

def get_detection_performance_analytics():
    """
    Get analytics on detection system performance for monitoring and improvement.
    
    Returns:
        dict: Performance metrics including accuracy, LLM usage, confidence analysis
    """
    conn = get_db_connection()
    try:
        # Get accuracy metrics from ground truth data
        accuracy_data = conn.execute("""
            SELECT 
                COUNT(*) as total_validations,
                SUM(CASE WHEN content LIKE '%correct_prediction": True%' THEN 1 ELSE 0 END) as correct_predictions,
                AVG(CASE WHEN content LIKE '%confidence%' THEN 
                    CAST(SUBSTR(content, INSTR(content, 'confidence": ') + 13, 4) AS FLOAT) 
                    ELSE NULL END) as avg_confidence
            FROM interaction_log 
            WHERE event_type = 'detection_ground_truth'
        """).fetchone()
        
        # Get LLM usage statistics
        llm_usage = conn.execute("""
            SELECT 
                COUNT(*) as total_decisions,
                SUM(CASE WHEN content LIKE '%llm_used": true%' OR content LIKE '%llm_used": True%' THEN 1 ELSE 0 END) as llm_used_count,
                COUNT(*) - SUM(CASE WHEN content LIKE '%llm_used": true%' OR content LIKE '%llm_used": True%' THEN 1 ELSE 0 END) as heuristic_only_count
            FROM interaction_log 
            WHERE event_type = 'document_detection_decision'
        """).fetchone()
        
        # Get recent detection decisions for trend analysis
        recent_decisions = conn.execute("""
            SELECT timestamp, content FROM interaction_log 
            WHERE event_type = 'document_detection_decision'
            ORDER BY timestamp DESC LIMIT 50
        """).fetchall()
        
        return {
            "accuracy": {
                "total_validations": accuracy_data[0] if accuracy_data[0] else 0,
                "correct_predictions": accuracy_data[1] if accuracy_data[1] else 0,
                "accuracy_rate": (accuracy_data[1] / accuracy_data[0]) if accuracy_data[0] and accuracy_data[0] > 0 else 0,
                "avg_confidence": accuracy_data[2] if accuracy_data[2] else 0
            },
            "llm_usage": {
                "total_decisions": llm_usage[0] if llm_usage[0] else 0,
                "llm_used_count": llm_usage[1] if llm_usage[1] else 0,
                "heuristic_only_count": llm_usage[2] if llm_usage[2] else 0,
                "llm_usage_rate": (llm_usage[1] / llm_usage[0]) if llm_usage[0] and llm_usage[0] > 0 else 0
            },
            "recent_decisions": [dict(row) for row in recent_decisions]
        }
        
    except sqlite3.Error as e:
        print(f"Database error while fetching performance analytics: {e}")
        return {"accuracy": {}, "llm_usage": {}, "recent_decisions": []}
    finally:
        if conn:
            conn.close()


# --- DOCUMENT TAGS UTILITIES ---
def store_document_tags(document_id, extracted_tags, llm_source='ollama'):
    """
    Store extracted tags for a document in the database.
    
    Args:
        document_id (int): The ID of the document in single_documents table
        extracted_tags (dict): Dictionary with tag categories as keys and lists of tag values
        llm_source (str): The LLM source that extracted the tags (default: 'ollama')
    
    Returns:
        int: Number of tags successfully stored
    """
    if not extracted_tags:
        return 0
    
    conn = get_db_connection()
    tags_stored = 0
    
    try:
        with conn:
            cursor = conn.cursor()
            
            # Clear existing tags for this document to avoid duplicates
            cursor.execute("DELETE FROM document_tags WHERE document_id = ?", (document_id,))
            
            # Insert new tags
            for category, tag_values in extracted_tags.items():
                if not tag_values:
                    continue
                    
                for tag_value in tag_values:
                    if tag_value and str(tag_value).strip():
                        try:
                            cursor.execute("""
                                INSERT INTO document_tags 
                                (document_id, tag_category, tag_value, llm_source)
                                VALUES (?, ?, ?, ?)
                            """, (document_id, category, str(tag_value).strip(), llm_source))
                            tags_stored += 1
                        except sqlite3.IntegrityError:
                            # Skip duplicate tags (unique constraint violation)
                            pass
            
    except sqlite3.Error as e:
        logging.error(f"💥 Database error storing tags for document {document_id}: {e}")
        tags_stored = 0
    finally:
        if conn:
            conn.close()
    
    return tags_stored


def get_document_tags(document_id):
    """
    Retrieve all tags for a specific document.
    
    Args:
        document_id (int): The document ID to fetch tags for
        
    Returns:
        dict: Dictionary with tag categories as keys and lists of tag values
    """
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        results = cursor.execute("""
            SELECT tag_category, tag_value, extraction_confidence, created_at
            FROM document_tags 
            WHERE document_id = ?
            ORDER BY tag_category, tag_value
        """, (document_id,)).fetchall()
        
        # Organize tags by category
        tags_dict = {
            'people': [],
            'organizations': [],
            'places': [],
            'dates': [],
            'document_types': [],
            'keywords': [],
            'amounts': [],
            'reference_numbers': []
        }
        
        for row in results:
            category, value, confidence, created_at = row
            if category in tags_dict:
                tags_dict[category].append(value)
        
        return tags_dict
        
    except sqlite3.Error as e:
        logging.error(f"💥 Database error fetching tags for document {document_id}: {e}")
        return {}
    finally:
        if conn:
            conn.close()


def find_similar_documents_by_tags(extracted_tags, limit=10, min_tag_matches=2):
    """
    Find documents with similar tag patterns for RAG context.
    
    Args:
        extracted_tags (dict): Tags to search for similarity
        limit (int): Maximum number of similar documents to return
        min_tag_matches (int): Minimum number of matching tags required
        
    Returns:
        list: List of similar documents with metadata
    """
    if not extracted_tags:
        return []
    
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        similar_docs = []
        
        # Build query to find documents with matching tags
        for category, values in extracted_tags.items():
            if not values:
                continue
                
            # Create placeholders for the IN clause
            placeholders = ','.join(['?' for _ in values])
            
            # Find documents with matching tags in this category
            query = f"""
                SELECT DISTINCT 
                    d.id, d.final_category, d.final_filename, d.ai_suggested_category,
                    d.created_at, COUNT(t.tag_value) as tag_matches,
                    GROUP_CONCAT(t.tag_value, ', ') as matching_tags
                FROM single_documents d
                JOIN document_tags t ON d.id = t.document_id
                WHERE t.tag_category = ? AND t.tag_value IN ({placeholders})
                GROUP BY d.id
                HAVING tag_matches >= ?
                ORDER BY tag_matches DESC, d.created_at DESC
                LIMIT ?
            """
            
            results = cursor.execute(query, [category] + values + [min_tag_matches, limit]).fetchall()
            
            for row in results:
                doc_id, final_category, final_filename, ai_suggested_category, created_at, tag_matches, matching_tags = row
                similar_docs.append({
                    'document_id': doc_id,
                    'final_category': final_category,
                    'final_filename': final_filename,
                    'ai_suggested_category': ai_suggested_category,
                    'tag_category': category,
                    'tag_matches': tag_matches,
                    'matching_tags': matching_tags.split(', ') if matching_tags else [],
                    'created_at': created_at
                })
        
        # Deduplicate and sort by relevance
        unique_docs = {}
        for doc in similar_docs:
            doc_id = doc['document_id']
            if doc_id not in unique_docs or doc['tag_matches'] > unique_docs[doc_id]['tag_matches']:
                unique_docs[doc_id] = doc
        
        # Return top results sorted by tag matches
        return sorted(unique_docs.values(), key=lambda x: x['tag_matches'], reverse=True)[:limit]
        
    except sqlite3.Error as e:
        logging.error(f"💥 Database error finding similar documents by tags: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_tag_usage_stats(category=None, limit=50):
    """
    Get statistics about tag usage patterns.
    
    Args:
        category (str, optional): Specific tag category to analyze
        limit (int): Maximum number of results to return
        
    Returns:
        list: Tag usage statistics
    """
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        if category:
            results = cursor.execute("""
                SELECT * FROM tag_usage_stats 
                WHERE tag_category = ?
                ORDER BY usage_count DESC
                LIMIT ?
            """, (category, limit)).fetchall()
        else:
            results = cursor.execute("""
                SELECT * FROM tag_usage_stats 
                ORDER BY usage_count DESC
                LIMIT ?
            """, (limit,)).fetchall()
        
        return [dict(row) for row in results]
        
    except sqlite3.Error as e:
        logging.error(f"💥 Database error fetching tag usage stats: {e}")
        return []
    finally:
        if conn:
            conn.close()


def analyze_tag_classification_patterns():
    """
    Analyze which tag patterns correlate with successful classifications.
    
    Returns:
        dict: Analysis of tag patterns and their classification accuracy
    """
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        # Find strong tag-to-category correlations
        patterns = cursor.execute("""
            SELECT 
                d.final_category,
                t.tag_category,
                t.tag_value,
                COUNT(*) as frequency,
                COUNT(CASE WHEN d.ai_suggested_category = d.final_category THEN 1 END) as ai_correct,
                COUNT(CASE WHEN d.ai_suggested_category != d.final_category THEN 1 END) as ai_incorrect,
                AVG(d.ai_confidence) as avg_ai_confidence
            FROM single_documents d
            JOIN document_tags t ON d.id = t.document_id
            WHERE d.final_category IS NOT NULL 
            AND d.ai_suggested_category IS NOT NULL
            GROUP BY d.final_category, t.tag_category, t.tag_value
            HAVING frequency >= 3
            ORDER BY frequency DESC
        """).fetchall()
        
        strong_patterns = []
        for row in patterns:
            final_cat, tag_cat, tag_val, freq, correct, incorrect, avg_conf = row
            total_predictions = correct + incorrect
            
            if total_predictions > 0:
                accuracy = correct / total_predictions
                if accuracy >= 0.8 and freq >= 5:  # High accuracy with sufficient sample size
                    strong_patterns.append({
                        'tag_category': tag_cat,
                        'tag_value': tag_val,
                        'predicted_category': final_cat,
                        'accuracy': accuracy,
                        'sample_size': freq,
                        'avg_confidence': avg_conf
                    })
        
        # Category-level tag analysis
        category_patterns = cursor.execute("""
            SELECT 
                d.final_category,
                COUNT(DISTINCT d.id) as document_count,
                COUNT(t.id) as total_tags,
                COUNT(DISTINCT t.tag_value) as unique_tags,
                AVG(CASE WHEN d.ai_suggested_category = d.final_category THEN 1.0 ELSE 0.0 END) as classification_accuracy
            FROM single_documents d
            LEFT JOIN document_tags t ON d.id = t.document_id
            WHERE d.final_category IS NOT NULL
            GROUP BY d.final_category
            ORDER BY document_count DESC
        """).fetchall()
        
        return {
            'strong_tag_patterns': strong_patterns,
            'category_analysis': [dict(row) for row in category_patterns],
            'pattern_count': len(strong_patterns)
        }
        
    except sqlite3.Error as e:
        logging.error(f"💥 Database error analyzing tag classification patterns: {e}")
        return {'strong_tag_patterns': [], 'category_analysis': [], 'pattern_count': 0}
    finally:
        if conn:
            conn.close()
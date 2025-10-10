"""
Batch Guard Functions

Prevents duplicate batch creation and provides safe batch management.
"""

import logging
from typing import Optional, List, Dict, Any
import sys
import os

# Add the parent directory to the path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from processing import database_connection
except ImportError:
    # Fallback for standalone execution
    import sqlite3
    from contextlib import contextmanager
    
    @contextmanager
    def database_connection():
        """Fallback database connection."""
        db_path = os.path.join(os.path.dirname(__file__), 'documents.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


def find_existing_processing_batch() -> Optional[int]:
    """
    Find any existing batch in 'processing' status.
    
    Returns:
        int: Batch ID if found, None otherwise
    """
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM batches 
                WHERE status = 'processing' 
                ORDER BY id DESC 
                LIMIT 1
            """)
            result = cursor.fetchone()
            return result[0] if result else None
            
    except Exception as e:
        logging.error(f"Error finding existing processing batch: {e}")
        return None


def _ensure_lastrowid(cursor) -> int:
    """Return a safe int for cursor.lastrowid or raise RuntimeError."""
    val = getattr(cursor, 'lastrowid', None)
    if val is None:
        raise RuntimeError("Database did not provide lastrowid after INSERT")
    return int(val)


def check_batch_has_documents(batch_id: int) -> bool:
    """
    Check if a batch has any documents.
    
    Args:
        batch_id: ID of the batch to check
        
    Returns:
        bool: True if batch has documents
    """
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM single_documents WHERE batch_id = ?
            """, (batch_id,))
            count = cursor.fetchone()[0]
            return count > 0
            
    except Exception as e:
        logging.error(f"Error checking batch {batch_id} documents: {e}")
        return False


def get_or_create_processing_batch() -> int:
    """
    Get existing processing batch or create new one if none exists.
    This prevents duplicate batch creation.
    
    Returns:
        int: Batch ID to use for processing
    """
    try:
        # First, check for existing processing batch
        existing_batch_id = find_existing_processing_batch()
        
        if existing_batch_id:
            # Check if it has documents
            has_docs = check_batch_has_documents(existing_batch_id)
            
            if has_docs:
                logging.info(f"🔄 Found existing processing batch {existing_batch_id} with documents - resuming")
                return existing_batch_id
            else:
                # Empty processing batch - can reuse it
                logging.info(f"♻️  Found empty processing batch {existing_batch_id} - reusing")
                return existing_batch_id
        
        # No existing processing batch, create new one
        with database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO batches (status) VALUES (?)
            """, ("processing",))
            new_batch_id = _ensure_lastrowid(cursor)
            conn.commit()
            
            logging.info(f"✨ Created new processing batch {new_batch_id}")
            return new_batch_id
            
    except Exception as e:
        logging.error(f"Error in get_or_create_processing_batch: {e}")
        # Fallback - create new batch
        try:
            with database_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO batches (status) VALUES (?)
                """, ("processing",))
                fallback_batch_id = _ensure_lastrowid(cursor)
                conn.commit()
                logging.warning(f"Created fallback batch {fallback_batch_id}")
                return fallback_batch_id
        except Exception as fallback_error:
            logging.error(f"Fallback batch creation failed: {fallback_error}")
            raise


def find_existing_intake_batch() -> Optional[int]:
    """
    Find an existing intake/ready batch (not exported) to reuse for intake operations.

    Returns:
        int: Batch ID if found, None otherwise
    """
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM batches
                WHERE status IN ('intake','ready')
                ORDER BY id DESC LIMIT 1
            """)
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception as e:
        logging.error(f"Error finding existing intake batch: {e}")
        return None


def get_or_create_intake_batch() -> int:
    """
    Return an existing intake/ready batch or create one if none exists.

    This mirrors get_or_create_processing_batch behaviour but for intake workflows.
    """
    try:
        existing = find_existing_intake_batch()
        if existing:
            logging.info(f"♻️  Reusing existing intake batch {existing}")
            return existing

        with database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO batches (status) VALUES (?)", ("intake",))
            new_id = _ensure_lastrowid(cursor)
            conn.commit()
            logging.info(f"✨ Created new intake batch {new_id}")
            return new_id
    except Exception as e:
        logging.error(f"Error creating intake batch: {e}")
        # Fallback: try to create raw insert
        try:
            with database_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO batches VALUES (NULL, 'intake')")
                new_id = _ensure_lastrowid(cursor)
                conn.commit()
                return new_id
        except Exception as e2:
            logging.error(f"Fallback intake batch creation failed: {e2}")
            raise


def create_new_batch(status: str) -> int:
    """
    Create a new batch row with the provided status and return its ID.

    Centralizes INSERT semantics so callers don't duplicate raw SQL and so
    we have a single place to audit/guard batch creation in future.
    """
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO batches (status) VALUES (?)", (status,))
            new_id = _ensure_lastrowid(cursor)
            conn.commit()
            logging.info(f"✨ Created new batch {new_id} with status '{status}'")
            return new_id
    except Exception as e:
        logging.error(f"Error creating new batch with status '{status}': {e}")
        # Attempt a minimal fallback insert
        try:
            with database_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO batches VALUES (NULL, ?)", (status,))
                new_id = _ensure_lastrowid(cursor)
                conn.commit()
                logging.warning(f"Fallback created new batch {new_id} with status '{status}'")
                return new_id
        except Exception as e2:
            logging.error(f"Fallback new batch creation also failed: {e2}")
            raise


def cleanup_empty_processing_batches() -> List[int]:
    """
    Clean up any processing batches that have no documents.
    
    Returns:
        list: IDs of batches that were cleaned up
    """
    cleaned_batches = []
    
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            
            # Find processing batches with no documents
            cursor.execute("""
                SELECT b.id 
                FROM batches b
                LEFT JOIN single_documents sd ON b.id = sd.batch_id
                WHERE b.status = 'processing' AND sd.batch_id IS NULL
            """)
            empty_batches = [row[0] for row in cursor.fetchall()]
            
            # Delete empty processing batches
            for batch_id in empty_batches:
                cursor.execute("DELETE FROM batches WHERE id = ?", (batch_id,))
                cleaned_batches.append(batch_id)
                logging.info(f"🧹 Cleaned up empty processing batch {batch_id}")
            
            conn.commit()
            
    except Exception as e:
        logging.error(f"Error cleaning up empty batches: {e}")
    
    return cleaned_batches


def get_batch_guard_info() -> Dict[str, Any]:
    """
    Get information about batch guard status for debugging.
    
    Returns:
        dict: Guard status information
    """
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            
            # Get processing batches
            cursor.execute("""
                SELECT b.id, COUNT(sd.id) as doc_count
                FROM batches b
                LEFT JOIN single_documents sd ON b.id = sd.batch_id
                WHERE b.status = 'processing'
                GROUP BY b.id
                ORDER BY b.id
            """)
            processing_batches = [{"batch_id": row[0], "document_count": row[1]} for row in cursor.fetchall()]
            
            # Get total batches
            cursor.execute("SELECT COUNT(*) FROM batches")
            total_batches = cursor.fetchone()[0]
            
            return {
                "total_batches": total_batches,
                "processing_batches": processing_batches,
                "processing_count": len(processing_batches),
                "has_guard_issues": len(processing_batches) > 1
            }
            
    except Exception as e:
        logging.error(f"Error getting batch guard info: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    # Demo the batch guard
    print("🛡️  Batch Guard Status")
    print("=" * 30)
    
    info = get_batch_guard_info()
    print(f"Total Batches: {info.get('total_batches', 'unknown')}")
    print(f"Processing Batches: {info.get('processing_count', 'unknown')}")
    
    if info.get('has_guard_issues'):
        print("⚠️  WARNING: Multiple processing batches detected!")
        for batch in info.get('processing_batches', []):
            print(f"  Batch {batch['batch_id']}: {batch['document_count']} documents")
        
        print("\n🧹 Cleaning up empty batches...")
        cleaned = cleanup_empty_processing_batches()
        if cleaned:
            print(f"Cleaned up batches: {cleaned}")
        else:
            print("No empty batches to clean")
    else:
        print("✅ Batch guard status: OK")
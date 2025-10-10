"""
Batch Guard Functions

Prevents duplicate batch creation and provides safe batch management.
"""

import logging
from typing import Optional, List, Dict, Any
import sys
import os
import shutil
import threading

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


def _is_retention_guard_enabled() -> bool:
    """
    Determine whether the retention guard is enabled.

    This prefers an explicit environment variable so tests can override the
    behavior via monkeypatch.setenv('ENFORCE_RETENTION_GUARD', ...). If the
    env var is not present, fall back to the runtime AppConfig instance.
    """
    val = os.getenv('ENFORCE_RETENTION_GUARD')
    if val is not None:
        return str(val).lower() in ('1', 'true', 't', 'yes')
    try:
        from config_manager import app_config
        return getattr(app_config, 'ENFORCE_RETENTION_GUARD', False)
    except Exception:
        return False


def backup_originals_for_batch(batch_id: int) -> int:
    """
    Copy any original files referenced by single_documents for `batch_id`
    into a retention folder under doc_processor/originals_retention/<batch_id>/.

    Returns the number of files copied.
    """
    copied = 0
    try:
        # Use the configured DB_BACKUP_DIR if available, otherwise fall back to
        # the legacy doc_processor/originals_retention path (kept for compatibility).
        try:
            from config_manager import app_config
            retention_root = getattr(app_config, 'DB_BACKUP_DIR', None)
        except Exception:
            retention_root = None

        if not retention_root:
            retention_root = os.path.abspath(os.path.join(os.path.dirname(__file__), 'originals_retention'))

        os.makedirs(retention_root, exist_ok=True)

        with database_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT original_pdf_path FROM single_documents WHERE batch_id=?', (batch_id,))
            rows = cur.fetchall()
            for row in rows:
                # Row may be a sqlite3.Row or tuple
                path = None
                try:
                    path = row['original_pdf_path']
                except Exception:
                    path = row[0] if row else None

                if not path:
                    continue

                # Only copy if file exists
                if os.path.exists(path):
                    dest_dir = os.path.join(retention_root, str(batch_id))
                    os.makedirs(dest_dir, exist_ok=True)
                    try:
                        shutil.copy2(path, dest_dir)
                        copied += 1
                    except Exception as e:
                        logging.warning(f"Failed to copy {path} -> {dest_dir}: {e}")
                else:
                    logging.debug(f"Original path not found for backup: {path}")
    except Exception as e:
        logging.error(f"Error backing up originals for batch {batch_id}: {e}")

    return copied


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


def _prune_empty_intake_batches(keep_id: Optional[int] = None) -> List[int]:
    """
    Remove older empty intake/ready batches except for `keep_id`.
    Returns list of pruned batch ids.
    """
    pruned = []
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM batches WHERE status IN ('intake','ready') ORDER BY id DESC")
            rows = [r[0] for r in cursor.fetchall()]
            # keep the newest or explicit keep_id
            for bid in rows:
                if keep_id and bid == keep_id:
                    continue
                # skip the most recent record to avoid racing with callers
                if bid == rows[0]:
                    continue
                try:
                    cursor.execute('SELECT COUNT(*) FROM single_documents WHERE batch_id=?', (bid,))
                    cnt = cursor.fetchone()[0]
                except Exception:
                    continue
                if cnt == 0:
                    try:
                        from config_manager import app_config
                        retention_root = getattr(app_config, 'DB_BACKUP_DIR', None)
                        if not retention_root:
                            retention_root = os.path.join(os.path.dirname(__file__), 'originals_retention')
                        retention_path = os.path.join(retention_root, str(bid))
                        if getattr(app_config, 'ENFORCE_RETENTION_GUARD', False):
                            if not os.path.isdir(retention_path) or not os.listdir(retention_path):
                                logging.debug(f"Prune-skip batch {bid}: retention missing")
                                continue
                    except Exception:
                        # On config errors, skip pruning to be safe
                        continue
                    try:
                        cursor.execute('DELETE FROM batches WHERE id=?', (bid,))
                        pruned.append(bid)
                        logging.info(f"Pruned empty intake batch {bid}")
                    except Exception as e:
                        logging.debug(f"Failed pruning batch {bid}: {e}")
            try:
                conn.commit()
            except Exception:
                pass
    except Exception as e:
        logging.debug(f"_prune_empty_intake_batches error: {e}")
    return pruned


def get_or_create_intake_batch() -> int:
    """
    Return an existing intake/ready batch or create one if none exists.

    This mirrors get_or_create_processing_batch behaviour but for intake workflows.
    """
    try:
        # Fast path: check for existing intake/ready batch
        existing = find_existing_intake_batch()
        if existing:
            logging.info(f"♻️  Reusing existing intake batch {existing}")
            # Best-effort prune older empty intake batches to avoid accumulation
            try:
                _prune_empty_intake_batches(keep_id=existing)
            except Exception:
                logging.debug("Prune of old intake batches failed; continuing")
            return existing

        # To avoid race conditions under concurrent calls, serialize creation
        # using a process-local threading lock. The Flask test harness runs
        # concurrent requests as threads in the same process, so this prevents
        # duplicate INSERTs without requiring DB schema changes.
        global _intake_creation_lock
        if '_intake_creation_lock' not in globals():
            _intake_creation_lock = threading.Lock()

        with _intake_creation_lock:
            with database_connection() as conn:
                cursor = conn.cursor()
                # Re-check within the transaction. Also prune older empty intake/ready
                # batches so tests and long-running servers don't accumulate them.
                cursor.execute("SELECT id FROM batches WHERE status IN ('intake','ready') ORDER BY id DESC")
                rows = [r[0] for r in cursor.fetchall()]
                if rows:
                    newest = rows[0]
                    # prune older empty batches (best-effort)
                    for old_id in rows[1:]:
                        try:
                            cursor.execute('SELECT COUNT(*) FROM single_documents WHERE batch_id=?', (old_id,))
                            cnt = cursor.fetchone()[0]
                        except Exception as e:
                            logging.debug(f"Prune-check failed for batch {old_id}: {e}")
                            continue

                        if cnt == 0:
                            # Respect retention guard when deleting
                            try:
                                if _is_retention_guard_enabled():
                                    try:
                                        from config_manager import app_config
                                        retention_root = getattr(app_config, 'DB_BACKUP_DIR', None)
                                    except Exception:
                                        retention_root = None
                                    if not retention_root:
                                        retention_root = os.path.join(os.path.dirname(__file__), 'originals_retention')
                                    retention_path = os.path.join(retention_root, str(old_id))
                                    if not os.path.isdir(retention_path) or not os.listdir(retention_path):
                                        logging.debug(f"Prune-skip batch {old_id}: retention missing")
                                        continue
                            except Exception:
                                # On config errors, skip pruning to be safe
                                logging.debug(f"Prune-skip batch {old_id}: config error")
                                continue

                            try:
                                cursor.execute('DELETE FROM batches WHERE id=?', (old_id,))
                                logging.info(f"Pruned empty intake batch {old_id}")
                            except Exception as del_e:
                                logging.debug(f"Failed pruning batch {old_id}: {del_e}")
                    try:
                        conn.commit()
                    except Exception:
                        pass
                    logging.info(f"♻️  Reusing existing intake batch {newest} (post-lock check)")
                    return newest

                # No existing batch: safe to insert
                cursor.execute("INSERT INTO batches (status) VALUES (?)", ("intake",))
                new_id = _ensure_lastrowid(cursor)
                conn.commit()
                logging.info(f"✨ Created new intake batch {new_id}")
                return new_id
    except Exception as e:
        logging.error(f"Error creating intake batch: {e}")
        # Fallback: try a minimal raw insert (best-effort)
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
            # Note: If this batch remains empty, the startup cleanup / orphaning
            # workflow will mark or delete it per policy; this log helps trace origin.
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

            # Find processing batches and then check per-batch document counts.
            cursor.execute("SELECT id FROM batches WHERE status = 'processing'")
            processing_ids = [row[0] for row in cursor.fetchall()]

            # If the above returned nothing but an explicit DATABASE_PATH points to a file,
            # try a direct sqlite3 connection as a fallback. This helps tests that set
            # DATABASE_PATH after config_manager was loaded.
            if not processing_ids:
                try:
                    import sqlite3 as _sqlite
                    env_db = os.getenv('DATABASE_PATH')
                    if env_db and os.path.exists(env_db):
                        direct_conn = _sqlite.connect(env_db)
                        direct_cur = direct_conn.cursor()
                        direct_cur.execute("SELECT id FROM batches WHERE status = 'processing'")
                        processing_ids = [r[0] for r in direct_cur.fetchall()]
                        direct_conn.close()
                except Exception:
                    pass

            empty_batches = []
            for bid in processing_ids:
                try:
                    cursor.execute('SELECT COUNT(*) FROM single_documents WHERE batch_id=?', (bid,))
                    cnt = cursor.fetchone()[0]
                except Exception:
                    cnt = 0
                if cnt == 0:
                    empty_batches.append(bid)
            
            # Delete empty processing batches
            for batch_id in empty_batches:
                # If retention guard enabled, ensure retention copy exists before deleting
                try:
                    # Respect the env/test override helper
                    if _is_retention_guard_enabled():
                        try:
                            from config_manager import app_config
                            retention_root = getattr(app_config, 'DB_BACKUP_DIR', None)
                        except Exception:
                            retention_root = None
                        if not retention_root:
                            retention_root = os.path.join(os.path.dirname(__file__), 'originals_retention')
                        retention_path = os.path.join(retention_root, str(batch_id))
                        if not os.path.isdir(retention_path) or not os.listdir(retention_path):
                            logging.warning(f"Skipping deletion of batch {batch_id}: retention backup missing (expected: {retention_path})")
                            continue
                except Exception:
                    # If config can't be read for any reason, fall back to not deleting
                    logging.warning(f"Retention guard check failed for batch {batch_id}; skipping deletion as a safe default")
                    continue

                cursor.execute("DELETE FROM batches WHERE id = ?", (batch_id,))
                cleaned_batches.append(batch_id)
                logging.info(f"🧹 Cleaned up empty processing batch {batch_id}")
            
            conn.commit()
            
    except Exception as e:
        logging.error(f"Error cleaning up empty batches: {e}")
    
    return cleaned_batches


def mark_orphaned_empty_batches(orphan_status: str = "orphaned") -> List[int]:
    """
    Mark empty batches (no single_documents) with a special status instead of deleting them.

    Returns:
        list: IDs of batches that were marked orphaned
    """
    marked = []
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM batches ORDER BY id")
            for row in cursor.fetchall():
                bid = row[0]
                cursor.execute('SELECT COUNT(*) FROM single_documents WHERE batch_id=?', (bid,))
                sd_count = cursor.fetchone()[0]
                if sd_count == 0:
                    # Only change status if it's not already the orphan status
                    try:
                        cursor.execute('SELECT status FROM batches WHERE id=?', (bid,))
                        cur_status = cursor.fetchone()[0]
                    except Exception:
                        cur_status = None
                    if cur_status != orphan_status:
                        cursor.execute('UPDATE batches SET status=? WHERE id=?', (orphan_status, bid))
                        marked.append(bid)
                        logging.info(f"⚠️  Marked empty batch {bid} as '{orphan_status}'")
            conn.commit()
    except Exception as e:
        logging.error(f"Error marking orphaned batches: {e}")
    return marked


def cleanup_empty_batches_policy(age_minutes: int = 60, statuses: Optional[List[str]] = None) -> List[int]:
    """
    Policy-based cleanup: delete empty batches that are older than `age_minutes` and whose
    status is in `statuses`. If the `created_at` column exists it will be used to check age;
    otherwise rowid is used as a heuristic (older rowid -> older record).

    Returns:
        list: IDs of batches deleted
    """
    if statuses is None:
        statuses = ["processing", "pending", "ready_for_manipulation"]

    deleted = []
    try:
        import datetime
        threshold = datetime.datetime.utcnow() - datetime.timedelta(minutes=age_minutes)

        with database_connection() as conn:
            cursor = conn.cursor()

            # Determine if created_at column exists
            has_created_at = False
            try:
                cursor.execute("PRAGMA table_info(batches)")
                cols = [r[1] for r in cursor.fetchall()]
                has_created_at = 'created_at' in cols
            except Exception:
                has_created_at = False

            if has_created_at:
                cursor.execute(
                    """
                    SELECT id FROM batches
                    WHERE status IN ({})
                      AND id NOT IN (SELECT DISTINCT batch_id FROM single_documents)
                      AND datetime(created_at) <= ?
                    """.format(','.join('?' for _ in statuses)),
                    tuple(statuses) + (threshold.strftime('%Y-%m-%d %H:%M:%S'),)
                )
                candidates = [r[0] for r in cursor.fetchall()]
            else:
                # Fallback heuristic: delete empty batches with matching statuses and low rowid
                cursor.execute(
                    "SELECT id FROM batches WHERE status IN ({})".format(','.join('?' for _ in statuses)),
                    tuple(statuses)
                )
                all_ids = [r[0] for r in cursor.fetchall()]
                # Check emptiness and pick ones with smallest id (older)
                candidates = []
                for bid in all_ids:
                    cursor.execute('SELECT COUNT(*) FROM single_documents WHERE batch_id=?', (bid,))
                    if cursor.fetchone()[0] == 0:
                        candidates.append(bid)

            for bid in candidates:
                try:
                    # Backup originals defensively before deleting (even empty batches)
                    # If retention guard enabled, ensure retention copy exists before deleting
                    try:
                        from config_manager import app_config
                        retention_root = getattr(app_config, 'DB_BACKUP_DIR', None)
                        if not retention_root:
                            retention_root = os.path.join(os.path.dirname(__file__), 'originals_retention')
                        retention_path = os.path.join(retention_root, str(bid))
                        if getattr(app_config, 'ENFORCE_RETENTION_GUARD', True):
                            if not os.path.isdir(retention_path) or not os.listdir(retention_path):
                                logging.warning(f"Skipping policy deletion of batch {bid}: retention backup missing (expected: {retention_path})")
                                continue
                    except Exception:
                        logging.warning(f"Retention guard check failed for batch {bid}; skipping policy delete as a safe default")
                        continue

                    try:
                        # Backup originals defensively before deleting (even empty batches)
                        backup_originals_for_batch(bid)
                    except Exception as e:
                        logging.warning(f"Failed to backup originals for batch {bid} before policy delete: {e}")

                    cursor.execute('DELETE FROM batches WHERE id=?', (bid,))
                    deleted.append(bid)
                    logging.info(f"🧹 Policy-cleaned empty batch {bid} (status in {statuses})")
                except Exception as e:
                    logging.error(f"Failed to delete batch {bid}: {e}")

            conn.commit()
    except Exception as e:
        logging.error(f"Error in cleanup_empty_batches_policy: {e}")

    # Log a warning if we deleted any batches so operators are aware
    if deleted:
        logging.warning(f"Deleted empty batches per policy: {deleted}")

    return deleted


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
"""Small helper to centralize DB connection behavior for dev tools.

If the requested path matches the configured application DB, prefer the
central `get_db_connection()` so PRAGMAs, WAL mode, and safety guards apply.
Otherwise fall back to a direct sqlite3.connect for arbitrary files.
"""
import os
import sqlite3

def connect(path, timeout=30.0, uri=False):
    """Return a sqlite3.Connection for the given path.

    If the resolved path equals the app_config.DATABASE_PATH, import and
    return doc_processor.database.get_db_connection() so dev scripts benefit
    from the same safeguards as the application. Otherwise return a normal
    sqlite3.connect to allow read-only checks and file scanning.
    """
    try:
        from doc_processor.config_manager import app_config
        cfg = getattr(app_config, 'DATABASE_PATH', None)
        if cfg and os.path.abspath(cfg) == os.path.abspath(path):
            # Import late to avoid cycles during packaging/import-time
            from doc_processor.database import get_db_connection
            return get_db_connection()
    except Exception:
        pass
    # Fallback direct connect (allow uri mode for file:... uses)
    return sqlite3.connect(path, timeout=timeout, uri=uri)

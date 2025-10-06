import os
import tempfile
import sqlite3
import pytest
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def temp_db_path(tmp_path, monkeypatch):
    """Provide fresh temp DB path and force config reload to use it."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    # Force config_manager to pick up new path by reloading module
    import importlib
    try:
        from doc_processor import config_manager
        importlib.reload(config_manager)
    except Exception:
        pass
    return db_path


@pytest.fixture()
def app(temp_db_path):
    """Create a Flask app bound to the isolated temp database.

    The caller is responsible for seeding any required tables/rows. We delay
    import until after DATABASE_PATH is set to avoid binding to production DB.
    """
    from doc_processor.app import create_app  # imported late
    application = create_app()
    return application


@pytest.fixture()
def client(app):
    """Flask test client fixture."""
    return app.test_client()


@pytest.fixture()
def seed_conn(temp_db_path):
    """Open a connection to the temp DB for seeding and yield it (auto-close)."""
    conn = sqlite3.connect(temp_db_path)
    try:
        yield conn
    finally:
        conn.close()


def ensure_minimal_grouped_schema(conn):
    """Create minimal tables needed for grouped-doc rotation tests."""
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER, document_name TEXT, status TEXT, final_filename_base TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS pages (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER, source_filename TEXT, page_number INTEGER, processed_image_path TEXT, ocr_text TEXT, ai_suggested_category TEXT, human_verified_category TEXT, status TEXT, rotation_angle INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS document_pages (document_id INTEGER, page_id INTEGER, sequence INTEGER, PRIMARY KEY(document_id,page_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS intake_rotations (filename TEXT PRIMARY KEY, rotation INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()

import os
import sqlite3
import sys
from pathlib import Path

import pytest

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _force_skip_ollama(monkeypatch):
    """Force tests to skip real Ollama calls unless explicitly overridden."""
    monkeypatch.setenv('SKIP_OLLAMA', '1')
    try:
        from doc_processor import config_manager
        setattr(config_manager.app_config, 'SKIP_OLLAMA', True)
    except Exception:
        # best-effort; env var is sufficient
        pass
    yield


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
def allow_db_creation(monkeypatch, temp_db_path):
    """Ensure the temporary DB has the minimal schema used by integration tests."""
    monkeypatch.setenv('ALLOW_NEW_DB', '1')
    conn = sqlite3.connect(str(temp_db_path))
    cur = conn.cursor()
    # Minimal tables used across integration tests
    cur.execute("""
    CREATE TABLE IF NOT EXISTS batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT,
        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS single_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER,
        original_filename TEXT,
        original_pdf_path TEXT,
        page_count INTEGER,
        file_size_bytes INTEGER,
        status TEXT,
        ai_suggested_category TEXT,
        ai_suggested_filename TEXT,
        ai_confidence REAL,
        ai_summary TEXT,
        ocr_text TEXT,
        ocr_confidence_avg REAL
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS document_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        tag_category TEXT CHECK(tag_category IN ('people','organizations','places','dates','document_types','keywords','amounts','reference_numbers')),
        tag_value TEXT,
        extraction_confidence REAL,
        llm_source TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(document_id, tag_category, tag_value)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        is_active INTEGER DEFAULT 1
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS interaction_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER,
        document_id INTEGER,
        event_type TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER,
        source_filename TEXT,
        page_number INTEGER
    )
    """)
    # Optional extra table used by some code paths
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tag_usage_stats (
        tag TEXT PRIMARY KEY,
        usage_count INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()
    yield


@pytest.fixture()
def temp_intake_dir(tmp_path, monkeypatch):
    intake = tmp_path / "intake"
    intake.mkdir()
    monkeypatch.setenv("INTAKE_DIR", str(intake))
    return str(intake)


@pytest.fixture()
def app(temp_db_path, allow_db_creation, temp_intake_dir, monkeypatch):
    """Create a Flask app bound to the isolated temp database.

    The caller is responsible for seeding any required tables/rows. We delay
    import until after DATABASE_PATH is set to avoid binding to production DB.
    """
    # Use FAST_TEST_MODE to speed tests
    monkeypatch.setenv("FAST_TEST_MODE", "1")
    # Ensure config_manager picks up test env overrides set by earlier fixtures
    import importlib
    try:
        import doc_processor.config_manager as _cm
        importlib.reload(_cm)
    except Exception:
        pass

    from doc_processor.app import create_app  # imported late
    application = create_app()
    yield application


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


@pytest.fixture()
def mocked_ollama(request, monkeypatch):
    """Compatibility fixture: some older tests request `mocked_ollama`.

    Reuse the package-level `mock_llm` fixture behavior by importing it
    if available. This keeps test expectations stable while centralizing
    the real mocking logic in `doc_processor/conftest.py`.
    """
    # If the package-level fixture `mock_llm` exists, call it.
    # Otherwise provide a no-op mock that ensures `_query_ollama` won't
    # perform network calls in practice (best-effort).
    # Ask pytest for the package-level `mock_llm` fixture if available so
    # pytest can manage its setup/teardown lifecycle. This avoids directly
    # calling fixture functions which pytest disallows.
    try:
        request.getfixturevalue('mock_llm')
        # If the above succeeded, the package-level fixture is active for
        # the duration of this test and we can simply yield control.
        yield
        return
    except Exception:
        # If the package-level fixture isn't available, fall back.
        pass

    # Fallback: ensure `_query_ollama` is stubbed to return an empty string.
    try:
        import doc_processor.llm_utils as _llm_utils

        monkeypatch.setattr(_llm_utils, '_query_ollama', lambda *a, **k: "")
    except Exception:
        # Nothing else we can do — tests will rely on SKIP_OLLAMA autouse.
        pass
    yield


# Global warning filters for FAST_TEST_MODE to reduce noisy OCR-related deprecations.
if os.getenv('FAST_TEST_MODE','0').lower() in ('1','true','t'):
    import warnings
    warnings.filterwarnings('ignore', category=DeprecationWarning, module=r'pytesseract')
    warnings.filterwarnings('ignore', category=DeprecationWarning, module=r'easyocr')
    warnings.filterwarnings('ignore', category=DeprecationWarning, message=r'.*SwigPy.*')

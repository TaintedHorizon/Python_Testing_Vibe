import os
import sqlite3
import sys
from pathlib import Path

import pytest

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ensure .env is loaded into the test process environment early so tests
# that read os.environ directly (rather than using config_manager) see the
# project defaults configured in `doc_processor/.env`.
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*a, **kw):
        return False

env_path = Path(__file__).resolve().parents[1] / '.env'
load_dotenv(dotenv_path=str(env_path))


@pytest.fixture(autouse=True)
def _prevent_copy_outside_intake(monkeypatch):
    """Prevent tests from copying fixtures into directories outside the
    configured `app_config.INTAKE_DIR`. This wraps `shutil.copyfile` and
    `shutil.copy2` to validate destination paths and fails fast if a test
    attempts to write outside the allowed intake directory.
    """
    try:
        from config_manager import app_config
    except Exception:
        # If config_manager can't be imported, skip protection (tests will
        # still fail later if misconfigured).
        yield
        return

    import shutil, os

    orig_copyfile = shutil.copyfile
    orig_copy2 = getattr(shutil, 'copy2', None)

    def _check_and_copyfile(src, dst, *a, **kw):
        intake = os.path.abspath(os.environ.get('INTAKE_DIR') or app_config.INTAKE_DIR)
        dst_dir = os.path.abspath(os.path.dirname(dst))
        # Only restrict writes into /mnt paths (mounted host intake) unless
        # the configured intake explicitly points there. Allow writes to
        # pytest tempdirs and backup dirs used by tests.
        if dst_dir.startswith('/mnt') and not dst_dir.startswith(intake):
            raise RuntimeError(f"Tests may only copy files into INTAKE_DIR ({intake}), attempted: {dst}")
        return orig_copyfile(src, dst, *a, **kw)

    monkeypatch.setattr(shutil, 'copyfile', _check_and_copyfile)

    if orig_copy2 is not None:
        def _check_and_copy2(src, dst, *a, **kw):
            intake = os.path.abspath(os.environ.get('INTAKE_DIR') or app_config.INTAKE_DIR)
            dst_dir = os.path.abspath(os.path.dirname(dst))
            if dst_dir.startswith('/mnt') and not dst_dir.startswith(intake):
                raise RuntimeError(f"Tests may only copy files into INTAKE_DIR ({intake}), attempted: {dst}")
            return orig_copy2(src, dst, *a, **kw)

        monkeypatch.setattr(shutil, 'copy2', _check_and_copy2)

    yield


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


@pytest.fixture(autouse=True)
def hermetic_files_cleanup(tmp_path, monkeypatch):
    """Autouse fixture to remove test-created intake and filing artifacts.

    Runs after each test. Only deletes files inside safe test-owned
    directories (tmp dirs, configured `INTAKE_DIR`, and configured
    `FILING_CABINET_DIR` or DB-adjacent filing_cabinet). Protects
    against accidental deletion of host-mounted `/mnt` data unless the
    configured intake explicitly points there.
    """
    yield
    import logging, shutil, os

    try:
        from doc_processor import config_manager
        app_cfg = config_manager.app_config
    except Exception:
        app_cfg = None

    def _safe_remove_tree(target_path):
        if not target_path:
            return
        try:
            target = os.path.abspath(str(target_path))
        except Exception:
            return

        # Protect mounted host areas unless explicitly configured
        intake_cfg = os.path.abspath(os.environ.get('INTAKE_DIR') or (getattr(app_cfg,'INTAKE_DIR', '') if app_cfg else ''))
        allowed_roots = [str(tmp_path), os.path.abspath('/tmp'), intake_cfg]
        # Normalize and check allowed prefixes
        if target.startswith('/mnt') and not any(target.startswith(p) and p for p in allowed_roots if p):
            logging.warning(f"Skipping cleanup for protected path outside intake: {target}")
            return

        if not os.path.exists(target):
            return

        # Remove files and subdirectories but avoid removing a non-test parent
        for root, dirs, files in os.walk(target, topdown=False):
            for name in files:
                fp = os.path.join(root, name)
                try:
                    os.remove(fp)
                except Exception:
                    logging.debug(f"Could not remove file during cleanup: {fp}")
            for name in dirs:
                dp = os.path.join(root, name)
                try:
                    shutil.rmtree(dp)
                except Exception:
                    logging.debug(f"Could not remove dir during cleanup: {dp}")

    # Primary targets: configured intake and configured filing cabinet
    try:
        intake_target = os.environ.get('INTAKE_DIR') or (getattr(app_cfg, 'INTAKE_DIR', None) if app_cfg else None)
        filing_target = os.environ.get('FILING_CABINET_DIR') or (getattr(app_cfg, 'FILING_CABINET_DIR', None) if app_cfg else None)
    except Exception:
        intake_target = os.environ.get('INTAKE_DIR')
        filing_target = os.environ.get('FILING_CABINET_DIR')

    _safe_remove_tree(intake_target)
    _safe_remove_tree(filing_target)

    # Also attempt DB-adjacent filing_cabinet cleanup when DATABASE_PATH is set
    db_path = os.environ.get('DATABASE_PATH') or os.environ.get('E2E_SERVER_DB') or (getattr(app_cfg, 'DATABASE_PATH', None) if app_cfg else None)
    try:
        if db_path:
            db_dir = os.path.dirname(db_path)
            _safe_remove_tree(os.path.join(db_dir, 'filing_cabinet'))
    except Exception:
        pass

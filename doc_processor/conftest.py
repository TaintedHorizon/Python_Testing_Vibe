import os
import pytest
import tempfile
from dotenv import load_dotenv

# Load .env early so test runs respect runtime GPU flags and other settings.
# If OLLAMA_NUM_GPU=0 we force CPU-only for torch by clearing CUDA_VISIBLE_DEVICES.
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
try:
    num_gpu = int(os.getenv('OLLAMA_NUM_GPU', '0'))
except Exception:
    num_gpu = 0

if num_gpu == 0:
    # Prevent torch from seeing any GPUs in tests
    os.environ['CUDA_VISIBLE_DEVICES'] = ''

# During pytest runs we must avoid creating or mutating the production database
# from `.env`. Force tests to use an isolated temporary database path and allow
# creation so the suite can initialize schemas without requiring manual flags.
try:
    import tempfile as _tempfile
    _tmp_db = os.path.join(_tempfile.gettempdir(), f"pytest_documents_{os.getpid()}.db")
    # Only override DATABASE_PATH if tests or environment haven't explicitly set one for CI.
    # This protects CI setups that intentionally point to a test DB via env.
    db_env = os.getenv('DATABASE_PATH')
    if not db_env or (isinstance(db_env, str) and db_env.startswith('/mnt')):
        os.environ['DATABASE_PATH'] = _tmp_db
    # Allow test runs to create the DB and enable fast test mode
    os.environ.setdefault('ALLOW_NEW_DB', '1')
    os.environ.setdefault('FAST_TEST_MODE', '1')
    # Ensure a minimal schema exists immediately so import-time code can run.
    try:
        import sqlite3 as _sqlite3
        _db_dir = os.path.dirname(_tmp_db)
        if _db_dir and not os.path.exists(_db_dir):
            os.makedirs(_db_dir, exist_ok=True)
        _conn = _sqlite3.connect(_tmp_db, timeout=30.0)
        _cur = _conn.cursor()
        # Create core tables used across many tests
        _cur.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'processing',
            has_been_manipulated INTEGER DEFAULT 0
        );
        """)
        _cur.execute("""
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            source_filename TEXT,
            page_number INTEGER,
            processed_image_path TEXT,
            ocr_text TEXT,
            ai_suggested_category TEXT,
            human_verified_category TEXT,
            status TEXT,
            rotation_angle INTEGER DEFAULT 0
        );
        """)
        _cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            document_name TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            final_filename_base TEXT
        );
        """)
        _cur.execute("""
        CREATE TABLE IF NOT EXISTS document_pages (
            document_id INTEGER,
            page_id INTEGER,
            sequence INTEGER,
            PRIMARY KEY(document_id, page_id)
        );
        """)
        _cur.execute("""
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
        );
        """)
        _cur.execute("""
        CREATE TABLE IF NOT EXISTS document_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            tag_category TEXT,
            tag_value TEXT
        );
        """)
        _cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_active INTEGER DEFAULT 1
        );
        """)
        _cur.execute("""
        CREATE TABLE IF NOT EXISTS interaction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            document_id INTEGER,
            user_id TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT,
            step TEXT,
            content TEXT,
            notes TEXT
        );
        """)
        _cur.execute("""
        CREATE TABLE IF NOT EXISTS intake_rotations (
            filename TEXT PRIMARY KEY,
            rotation INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        _cur.execute("""
        CREATE TABLE IF NOT EXISTS intake_working_files (
            filename TEXT PRIMARY KEY,
            working_pdf TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        _conn.commit()
        _conn.close()
    except Exception:
        pass
except Exception:
    pass


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a unique temporary database path for tests."""
    p = tmp_path / f"test_db_{os.getpid()}.db"
    return str(p)


@pytest.fixture
def allow_db_creation(monkeypatch, temp_db_path):
    """Set environment to use the temporary DB and allow creation during tests.

    This fixture sets DATABASE_PATH and ALLOW_NEW_DB so tests that call
    `get_db_connection()` won't attempt to create or overwrite the repo DB.
    """
    monkeypatch.setenv('DATABASE_PATH', temp_db_path)
    monkeypatch.setenv('ALLOW_NEW_DB', '1')
    # Initialize a minimal schema tailored for tests (avoid importing dev_tools helpers)
    try:
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        cur = conn.cursor()

        # Minimal tables required by many integration tests
        cur.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'processing',
            has_been_manipulated INTEGER DEFAULT 0
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS single_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            original_filename TEXT NOT NULL,
            original_pdf_path TEXT,
            searchable_pdf_path TEXT,
            markdown_path TEXT,
            page_count INTEGER NOT NULL,
            file_size_bytes INTEGER,
            ocr_text TEXT,
            ocr_confidence_avg REAL,
            ai_suggested_category TEXT,
            ai_suggested_filename TEXT,
            ai_confidence REAL,
            ai_summary TEXT,
            final_category TEXT,
            final_filename TEXT,
            status TEXT NOT NULL DEFAULT 'processing',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES batches(id)
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS document_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            tag_category TEXT NOT NULL CHECK(tag_category IN (
                'people', 'organizations', 'places', 'dates', 
                'document_types', 'keywords', 'amounts', 'reference_numbers'
            )),
            tag_value TEXT NOT NULL,
            extraction_confidence REAL DEFAULT 1.0,
            llm_source TEXT DEFAULT 'ollama',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES single_documents(id) ON DELETE CASCADE,
            UNIQUE(document_id, tag_category, tag_value)
        );
        """)

        # Some tests expect the tag_usage_stats view to exist
        try:
            cur.execute("""
            CREATE VIEW IF NOT EXISTS tag_usage_stats AS
            SELECT tag_category, tag_value, COUNT(*) as usage_count FROM document_tags GROUP BY tag_category, tag_value
            """)
        except Exception:
            # Views may not be supported in some minimal sqlite builds - ignore
            pass

        conn.commit()
        conn.close()
    except Exception:
        # If anything goes wrong here, tests will attempt on-demand schema creation
        pass
    yield temp_db_path
    # best-effort cleanup of the file after test
    try:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
    except Exception:
        pass

import os
import pytest

# Keep this conftest small: its purpose is to set global test environment and
# provide a mock LLM fixture. Test-local fixtures (temp DB, app, client) live in
# `doc_processor/tests/conftest.py` to avoid duplicate definitions and import-time
# side-effects.
try:
    # dotenv is optional; load if available so OLLAMA_NUM_GPU from .env is respected
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(env_path)
except Exception:
    pass

try:
    num_gpu = int(os.getenv('OLLAMA_NUM_GPU', '0'))
except Exception:
    num_gpu = 0

if num_gpu == 0:
    # Force CPU-only for tests when OLLAMA_NUM_GPU is 0
    os.environ['CUDA_VISIBLE_DEVICES'] = ''

# If running tests in FAST_TEST_MODE (or if pytest is driving the run), ensure
# an isolated temporary DATABASE_PATH is set at import-time so config_manager
# will pick it up and not point to the repository DB. This is defensive and
# intentionally overwrites only when FAST_TEST_MODE is enabled or DATABASE_PATH
# is not explicitly provided.
try:
    fast_flag = os.getenv('FAST_TEST_MODE', '0').lower() in ('1', 'true', 't')
except Exception:
    fast_flag = False

if fast_flag or os.getenv('PYTEST_CURRENT_TEST'):
    import tempfile
    tmp_db = os.path.join(tempfile.gettempdir(), f'doc_processor_pytest_{os.getpid()}.db')
    # Only override if DATABASE_PATH isn't explicitly set differently by CI/user
    if os.getenv('DATABASE_PATH') is None or fast_flag:
        os.environ['DATABASE_PATH'] = tmp_db
        os.environ['ALLOW_NEW_DB'] = '1'
        os.environ['OLLAMA_NUM_GPU'] = '0'
        os.environ['CUDA_VISIBLE_DEVICES'] = ''


@pytest.fixture
def mock_llm(monkeypatch):
    """Monkeypatch LLM-related calls to return deterministic values for tests.

    Avoids network calls to Ollama during unit tests and returns canned AI suggestions.
    """
    # Patch high-level processing helper if present
    try:
        import doc_processor.processing as _processing

        def _stub_get_ai_suggestions_for_document(ocr_text, filename, page_count, file_size_mb, document_id=None):
            return ("Uncategorized", "test_name", 0.5, "summary")

        monkeypatch.setattr(
            _processing, '_get_ai_suggestions_for_document', _stub_get_ai_suggestions_for_document
        )
    except Exception:
        pass

    # Also stub lower-level llm_utils to be safe
    try:
        import doc_processor.llm_utils as _llm_utils
        monkeypatch.setattr(_llm_utils, '_query_ollama', lambda *a, **k: "")
    except Exception:
        pass

    yield


@pytest.fixture(scope='session', autouse=True)
def _enforce_llm_stub():
    """Session autouse fixture to stub low-level LLM calls at import/collection time.

    This ensures any code paths that reach into `doc_processor.llm_utils._query_ollama`
    will hit a deterministic in-memory stub during tests and will not attempt
    network access to an Ollama server.
    """
    try:
        import doc_processor.llm_utils as _llm

        # Keep original in case some tests want to restore it manually.
        try:
            _llm._original_query_ollama = _llm._query_ollama
        except Exception:
            pass

        def _stub_query_ollama(*args, **kwargs):
            # Return a lightweight deterministic response shape used by callers.
            # Many callers only check for non-empty string or parse specific
            # keys; returning a short, parseable placeholder keeps behavior
            # predictable.
            return "TYPE: single_document\nCONFIDENCE: 90\nREASON: test-mode stub"

        _llm._query_ollama = _stub_query_ollama
    except Exception:
        # Best-effort: if the module can't be imported, tests will rely on
        # other existing mocks (e.g., SKIP_OLLAMA env) to avoid network.
        pass
    yield
    # No teardown required; test process exits after session. If the original
    # function was saved, restore it for completeness.
    try:
        import doc_processor.llm_utils as _llm2
        if hasattr(_llm2, '_original_query_ollama'):
            _llm2._query_ollama = _llm2._original_query_ollama
    except Exception:
        pass


@pytest.fixture(scope='session', autouse=True)
def _enforce_test_environment(tmp_path_factory):
    """Session-wide autouse fixture to ensure tests use an isolated temp DB and fast test flags.

    This prevents accidental use or overwrite of the repository's SQLite database
    during test collection or test runs. It sets DATABASE_PATH, ALLOW_NEW_DB and
    FAST_TEST_MODE before tests run.
    """
    tempdir = tmp_path_factory.mktemp('pytest_db_env')
    db_path = os.path.join(str(tempdir), 'documents.db')
    # Ensure parent dir exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    os.environ.setdefault('DATABASE_PATH', db_path)
    os.environ.setdefault('ALLOW_NEW_DB', '1')
    os.environ.setdefault('FAST_TEST_MODE', '1')
    # Ensure CPU-only for LLMs unless explicitly requested
    os.environ.setdefault('OLLAMA_NUM_GPU', '0')
    # Also clear CUDA_VISIBLE_DEVICES for safety
    os.environ.setdefault('CUDA_VISIBLE_DEVICES', '')
    yield



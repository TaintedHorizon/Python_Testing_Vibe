import os
import pytest
import tempfile


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
    yield temp_db_path
    # best-effort cleanup of the file after test
    try:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
    except Exception:
        pass

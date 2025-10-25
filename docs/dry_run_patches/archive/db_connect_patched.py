"""
Dry-run wrapper for `doc_processor/dev_tools/db_connect.py`.

Ensures `DATABASE_PATH` and `DB_BACKUP_DIR` point to test-scoped locations to avoid touching repo databases during tests.
Re-exports connection helpers where present.
"""
import os
from pathlib import Path

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        import tempfile
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
Path(base).mkdir(parents=True, exist_ok=True)

os.environ.setdefault('DATABASE_PATH', str(Path(base) / 'documents_test.db'))
os.environ.setdefault('DB_BACKUP_DIR', str(Path(base) / 'db_backups'))

try:
    from doc_processor.dev_tools import db_connect as _original  # type: ignore
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'dev_tools' / 'db_connect.py'
    spec = importlib.util.spec_from_file_location('db_connect', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load db_connect module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []
_tmp = getattr(_original, 'database_connection', None)
if _tmp is not None:
    database_connection = _tmp
    __all__.append('database_connection')
_tmp = getattr(_original, 'connect', None)
if _tmp is not None:
    connect = _tmp
    __all__.append('connect')

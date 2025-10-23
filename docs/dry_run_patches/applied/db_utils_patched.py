"""
Dry-run wrapper for `doc_processor/db_utils.py`.

Sets `DATABASE_PATH` and `DB_BACKUP_DIR` to a test-scoped location before importing the original module.
Re-exports common helpers (if present) without causing import-time writes.
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

# Test-scoped defaults
os.environ.setdefault('DATABASE_PATH', str(Path(base) / 'documents_test.db'))
os.environ.setdefault('DB_BACKUP_DIR', str(Path(base) / 'db_backups'))

try:
    from doc_processor import db_utils as _original
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'db_utils.py'
    spec = importlib.util.spec_from_file_location('db_utils', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load db_utils module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

# Re-export helpers commonly used in tests (guarded via getattr)
__all__ = []
_tmp = getattr(_original, 'database_connection', None)
if _tmp is not None:
    database_connection = _tmp
    __all__.append('database_connection')
_tmp = getattr(_original, 'create_backup', None)
if _tmp is not None:
    create_backup = _tmp
    __all__.append('create_backup')
_tmp = getattr(_original, 'restore_backup', None)
if _tmp is not None:
    restore_backup = _tmp
    __all__.append('restore_backup')

"""
Dry-run wrapper for `doc_processor/dev_tools/upgrade_full_schema.py`.

Sets test-scoped DATABASE_PATH and DB_BACKUP_DIR before importing and re-exports upgrade entrypoints.
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
os.environ.setdefault('LOG_FILE_PATH', str(Path(base) / 'upgrade_full_schema.log'))

try:
    from doc_processor.dev_tools import upgrade_full_schema as _original  # type: ignore
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'dev_tools' / 'upgrade_full_schema.py'
    spec = importlib.util.spec_from_file_location('upgrade_full_schema', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load upgrade_full_schema module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []
_tmp = getattr(_original, 'main', None)
if _tmp is not None:
    main = _tmp
    __all__.append('main')
_tmp = getattr(_original, 'upgrade', None)
if _tmp is not None:
    upgrade = _tmp
    __all__.append('upgrade')

"""
Dry-run wrapper for DB backup utilities (doc_processor/dev_tools or db backup helpers).

Sets DB_BACKUP_DIR and DATABASE_PATH to safe test-scoped paths before importing the real module.
Re-exports common helpers like `create_backup` and `restore_backup` where available.
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

os.environ.setdefault('DB_BACKUP_DIR', str(Path(base) / 'db_backups'))
os.environ.setdefault('DATABASE_PATH', str(Path(base) / 'documents.db'))

try:
    # The static analyzer may not resolve dev_tools submodules in some environments
    from doc_processor.dev_tools import db_backups as _original  # type: ignore
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'dev_tools' / 'db_backups.py'
    spec = importlib.util.spec_from_file_location('db_backups', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load db_backups module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []
_tmp = getattr(_original, 'create_backup', None)
if _tmp is not None:
    create_backup = _tmp
    __all__.append('create_backup')
_tmp = getattr(_original, 'restore_backup', None)
if _tmp is not None:
    restore_backup = _tmp
    __all__.append('restore_backup')

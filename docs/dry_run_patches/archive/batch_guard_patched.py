"""
Dry-run wrapper for `doc_processor/batch_guard.py` (or related batch-guard service).

Pre-sets test-safe paths before importing the original module, then re-exports commonly used symbols.
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

os.environ.setdefault('PROCESSED_DIR', str(Path(base) / 'processed'))
os.environ.setdefault('DB_BACKUP_DIR', str(Path(base) / 'db_backups'))
os.environ.setdefault('LOG_FILE_PATH', str(Path(base) / 'batch_guard.log'))

try:
    from doc_processor import batch_guard as _original
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'batch_guard.py'
    spec = importlib.util.spec_from_file_location('batch_guard', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load batch_guard module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []
_tmp = getattr(_original, 'BatchGuard', None)
if _tmp is not None:
    BatchGuard = _tmp
    __all__.append('BatchGuard')
_tmp = getattr(_original, 'guard_batch', None)
if _tmp is not None:
    guard_batch = _tmp
    __all__.append('guard_batch')
# Dry-run patched snippet for doc_processor/batch_guard.py
# Purpose: ensure retention_root and dest_dir prefer env/app_config or TEST_TMPDIR and are created safely
import os
import tempfile
try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.getenv('RETENTION_ROOT') or os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()

# Example usage:
retention_root = os.environ.get('RETENTION_ROOT') or select_tmp_dir()
try:
    os.makedirs(retention_root, exist_ok=True)
except Exception:
    pass

# For dest_dir mapping, use similar pattern

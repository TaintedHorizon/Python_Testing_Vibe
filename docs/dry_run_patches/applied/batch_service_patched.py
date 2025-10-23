"""
Dry-run wrapper for `doc_processor/services/batch_service.py`.

Sets test-safe defaults for DB_BACKUP_DIR, PROCESSED_DIR, FILING_CABINET_DIR and LOG_FILE_PATH
before importing the real batch service. Re-exports `BatchService` and `process_batch` where present.
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

for k in ('DB_BACKUP_DIR', 'PROCESSED_DIR', 'FILING_CABINET_DIR', 'LOG_FILE_PATH'):
    os.environ.setdefault(k, str(Path(base) / k.lower()))

try:
    from doc_processor.services import batch_service as _original
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'services' / 'batch_service.py'
    spec = importlib.util.spec_from_file_location('batch_service', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load batch_service module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

# Re-export common API (guarded, use getattr to keep static-checkers quiet)
__all__ = []
_tmp = getattr(_original, 'BatchService', None)
if _tmp is not None:
    BatchService = _tmp
    __all__.append('BatchService')
_tmp = getattr(_original, 'process_batch', None)
if _tmp is not None:
    process_batch = _tmp
    __all__.append('process_batch')
"""
Dry-run wrapper for `doc_processor/services/batch_service.py`.
Sets safe defaults for DB_BACKUP_DIR, PROCESSED_DIR, FILING_CABINET_DIR, and LOG_FILE_PATH before importing
and re-exports `BatchService` and `process_batch`.
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

for k in ('DB_BACKUP_DIR', 'PROCESSED_DIR', 'FILING_CABINET_DIR', 'LOG_FILE_PATH'):
    os.environ.setdefault(k, str(Path(base) / k.lower()))

try:
    from doc_processor.services import batch_service as _original
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'services' / 'batch_service.py'
    spec = importlib.util.spec_from_file_location('batch_service', str(fallback))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

if hasattr(_original, 'BatchService'):
    BatchService = _original.BatchService
if hasattr(_original, 'process_batch'):
    process_batch = _original.process_batch

__all__ = [name for name in ('BatchService', 'process_batch') if name in globals()]

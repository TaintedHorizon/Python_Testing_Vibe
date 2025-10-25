"""
Dry-run wrapper for `doc_processor/dev_tools/check_wip_status.py`.

Sets test-scoped environment variables before importing and re-exports diagnostic functions.
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

os.environ.setdefault('WIP_DIR', str(Path(base) / 'wip'))
os.environ.setdefault('PROCESSED_DIR', str(Path(base) / 'processed'))
os.environ.setdefault('LOG_FILE_PATH', str(Path(base) / 'check_wip_status.log'))

try:
    from doc_processor.dev_tools import check_wip_status as _original  # type: ignore
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'dev_tools' / 'check_wip_status.py'
    spec = importlib.util.spec_from_file_location('check_wip_status', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load check_wip_status module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []
_tmp = getattr(_original, 'main', None)
if _tmp is not None:
    main = _tmp
    __all__.append('main')
_tmp = getattr(_original, 'check', None)
if _tmp is not None:
    check = _tmp
    __all__.append('check')

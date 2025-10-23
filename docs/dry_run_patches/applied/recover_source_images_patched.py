"""
Dry-run wrapper for `doc_processor/dev_tools/recover_source_images.py`.

Sets test-scoped environment variables before importing and re-exports restore functions.
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
os.environ.setdefault('FILING_CABINET_DIR', str(Path(base) / 'filing_cabinet'))

try:
    from doc_processor.dev_tools import recover_source_images as _original  # type: ignore
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'dev_tools' / 'recover_source_images.py'
    spec = importlib.util.spec_from_file_location('recover_source_images', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load recover_source_images module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []
_tmp = getattr(_original, 'main', None)
if _tmp is not None:
    main = _tmp
    __all__.append('main')
_tmp = getattr(_original, 'restore_images', None)
if _tmp is not None:
    restore_images = _tmp
    __all__.append('restore_images')
"""
Dry-run wrapper for doc_processor/dev_tools/recover_source_images.py

Ensures `FILING_CABINET_DIR` points to a test-scoped directory before importing
the original module so file writes/read operations don't touch the repo.
"""
from __future__ import annotations

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
os.makedirs(base, exist_ok=True)
os.environ.setdefault('FILING_CABINET_DIR', os.path.join(base, 'filing_cabinet'))

from doc_processor.dev_tools.recover_source_images import main, recover_images  # type: ignore

__all__ = ['main', 'recover_images']

"""
Dry-run wrapper for `doc_processor/routes/manipulation.py`.

Redirects file-output related envs to `TEST_TMPDIR` before importing
the real module so tests won't write into repo-scoped locations.
"""
from __future__ import annotations

import os
from pathlib import Path
import importlib

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        import tempfile
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
Path(base).mkdir(parents=True, exist_ok=True)

os.environ.setdefault('PROCESSED_DIR', str(Path(base) / 'processed'))
os.environ.setdefault('INTAKE_DIR', str(Path(base) / 'intake'))
os.environ.setdefault('FILING_CABINET_DIR', str(Path(base) / 'filing_cabinet'))
os.environ.setdefault('LOG_FILE_PATH', str(Path(base) / 'routes_manipulation.log'))

try:
    from doc_processor.routes import manipulation as _original  # type: ignore
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[3]
    fallback = repo_root / 'doc_processor' / 'routes' / 'manipulation.py'
    spec = importlib.util.spec_from_file_location('doc_processor.routes.manipulation', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load manipulation module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []

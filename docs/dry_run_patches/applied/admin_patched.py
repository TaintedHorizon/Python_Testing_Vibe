"""
Dry-run wrapper for `doc_processor/routes/admin.py`.

Sets test-scoped `LOG_FILE_PATH`, `CACHE_DIR`, and test tmp fallbacks before importing
the admin blueprint. Re-exports `bp`.
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

# Safe defaults
os.environ.setdefault('LOG_FILE_PATH', os.path.join(base, 'logs', 'app.log'))
os.environ.setdefault('CACHE_DIR', os.path.join(base, 'analysis_cache'))
os.environ.setdefault('INTAKE_DIR', os.path.join(base, 'intake'))
os.environ.setdefault('PROCESSED_DIR', os.path.join(base, 'processed'))

from doc_processor.routes.admin import bp as bp  # type: ignore

__all__ = ['bp']


"""
Dry-run wrapper for doc_processor/dev_tools/purge_normalized_cache.py

Sets `NORMALIZED_DIR` to a test-scoped location before importing to avoid
purging normalized cache from the repo during tests.
"""
from __future__ import annotations

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir() -> str:
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
os.makedirs(base, exist_ok=True)
os.environ.setdefault('NORMALIZED_DIR', os.path.join(base, 'normalized'))

from doc_processor.dev_tools.purge_normalized_cache import main, purge_cache  # type: ignore

__all__ = ['main', 'purge_cache']

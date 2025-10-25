"""
Dry-run wrapper for doc_processor/dev_tools/cleanup_empty_batch_directories.py

Sets `PROCESSED_DIR` and `INTAKE_DIR` to test-scoped locations before importing
to avoid removing directories from the repository during tests.
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
os.environ.setdefault('PROCESSED_DIR', os.path.join(base, 'processed'))
os.environ.setdefault('INTAKE_DIR', os.path.join(base, 'intake'))

from doc_processor.dev_tools.cleanup_empty_batch_directories import main, cleanup_empty_dirs  # type: ignore

__all__ = ['main', 'cleanup_empty_dirs']

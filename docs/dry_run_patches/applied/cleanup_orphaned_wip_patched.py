"""
Dry-run wrapper for dev_tools/cleanup_orphaned_wip.py

Sets `PROCESSED_DIR` to a test-scoped directory (TEST_TMPDIR/select_tmp_dir)
before importing to avoid clearing repo-local processed files during tests.
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
os.environ.setdefault('PROCESSED_DIR', os.path.join(base, 'processed'))

from dev_tools.cleanup_orphaned_wip import main, find_orphaned_wip  # type: ignore

__all__ = ['main', 'find_orphaned_wip']

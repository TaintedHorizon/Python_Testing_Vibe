"""
Dry-run wrapper for `doc_processor/dev_tools/restore_categories.py`.

This sets `CATEGORIES_BACKUP_DIR` to a TEST_TMPDIR-scoped location before importing
so backups/read/write use a safe directory during tests.
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

os.environ.setdefault('CATEGORIES_BACKUP_DIR', os.path.join(base, 'dev_tool_backups'))

from doc_processor.dev_tools.restore_categories import main  # type: ignore

__all__ = ['main']

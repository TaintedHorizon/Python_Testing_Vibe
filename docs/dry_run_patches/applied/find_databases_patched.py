"""
Dry-run wrapper for dev_tools/find_databases.py

Ensures `DB_BACKUP_DIR` is set to a safe test-scoped directory before importing
the original module.
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
os.environ.setdefault('DB_BACKUP_DIR', os.path.join(base, 'db_backups'))

from dev_tools.find_databases import main, find_databases  # type: ignore

__all__ = ['main', 'find_databases']

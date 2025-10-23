"""
Dry-run wrapper for doc_processor/dev_tools/add_single_documents_table.py

Sets `DATABASE_PATH` and `DB_BACKUP_DIR` to test-scoped locations before
importing the original script to avoid modifying real DBs during tests.
"""
from __future__ import annotations

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir, ensure_dir
except Exception:
    def select_tmp_dir():
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()
    def ensure_dir(p: str):
        os.makedirs(p, exist_ok=True)

base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
ensure_dir(base)

# If DATABASE_PATH is not explicitly set, create a test DB under TEST_TMPDIR
if 'DATABASE_PATH' not in os.environ:
    os.environ['DATABASE_PATH'] = os.path.join(base, 'documents_single_test.db')

os.environ.setdefault('DB_BACKUP_DIR', os.path.join(base, 'db_backups'))

from doc_processor.dev_tools.add_single_documents_table import main, upgrade_database  # type: ignore

__all__ = ['main', 'upgrade_database']

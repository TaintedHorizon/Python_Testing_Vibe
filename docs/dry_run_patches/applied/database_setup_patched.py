"""
Dry-run wrapper for doc_processor/dev_tools/database_setup.py

Sets `DATABASE_PATH` and `DB_BACKUP_DIR` to test-scoped locations (prefer
`TEST_TMPDIR`) before importing the original module to avoid touching real
databases during tests/CI.
"""
from __future__ import annotations

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir() -> str:
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
ensure_dir(base)

# Respect an explicit DATABASE_PATH if provided; otherwise set a test DB
if 'DATABASE_PATH' not in os.environ:
    os.environ['DATABASE_PATH'] = os.path.join(base, 'documents_setup_test.db')

# Default DB backup dir to test-scoped
os.environ.setdefault('DB_BACKUP_DIR', os.path.join(base, 'db_backups'))

from doc_processor.dev_tools.database_setup import main, create_schema  # type: ignore

__all__ = ['main', 'create_schema']


"""
Dry-run wrapper for doc_processor/dev_tools/force_reset_batch.py

Sets `PROCESSED_DIR`, `FILING_CABINET_DIR`, and `DB_BACKUP_DIR` to test-scoped
locations before importing to avoid destructive actions in the repo during tests.
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
os.environ.setdefault('FILING_CABINET_DIR', os.path.join(base, 'filing_cabinet'))
os.environ.setdefault('DB_BACKUP_DIR', os.path.join(base, 'db_backups'))

from doc_processor.dev_tools.force_reset_batch import main, reset_batch  # type: ignore

__all__ = ['main', 'reset_batch']

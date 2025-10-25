"""
Dry-run wrapper for `doc_processor/app_original_backup.py`.

This sets test-scoped locations for logs, cache, and backups before importing the
original module so import-time file operations use safe paths during tests/CI.
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

# Test-scoped defaults
os.environ.setdefault('LOG_FILE_PATH', os.path.join(base, 'logs', 'app_original_backup.log'))
os.environ.setdefault('CACHE_DIR', os.path.join(base, 'cache'))
os.environ.setdefault('DB_BACKUP_DIR', os.path.join(base, 'db_backups'))
os.environ.setdefault('ARCHIVE_DIR', os.path.join(base, 'archive'))

# Import original module after env is prepared
from doc_processor import app_original_backup as original  # type: ignore

# Re-export commonly used entry points (if present)
main = getattr(original, 'main', None)
__all__ = ['original', 'main']

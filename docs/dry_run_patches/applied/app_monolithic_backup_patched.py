# Dry-run patched snippet for archive/app_backups/app_monolithic_backup.py
# Purpose: ensure LOG_DIR and backup paths prefer env/test tmp
import os
import tempfile
try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.getenv('BACKUP_DIR') or os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()

LOG_DIR = os.environ.get('LOG_DIR') or select_tmp_dir()
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except Exception:
    pass

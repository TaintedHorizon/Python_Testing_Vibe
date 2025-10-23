# Dry-run patched snippet for doc_processor/config_manager.py
# Purpose: ensure DB_BACKUP_DIR and other output dirs prefer env/test tmp and are created safely
import os
import tempfile
try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.getenv('DB_BACKUP_DIR') or os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()

# Example: when setting config.DB_BACKUP_DIR
# db_backup = os.environ.get('DB_BACKUP_DIR') or select_tmp_dir()
# os.makedirs(db_backup, exist_ok=True)

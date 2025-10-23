# Dry-run patched snippet for doc_processor/database.py
# Purpose: ensure backup_root and override_dir use app_config/env or TEST_TMPDIR and are created
import os
import tempfile
try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.getenv('DB_BACKUP_DIR') or os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()

# Example mapping

def ensure_backup_root(backup_root):
    mapped = os.environ.get('DB_BACKUP_DIR') or select_tmp_dir() or backup_root
    try:
        os.makedirs(mapped, exist_ok=True)
    except Exception:
        try:
            os.makedirs(backup_root, exist_ok=True)
            mapped = backup_root
        except Exception:
            pass
    return mapped

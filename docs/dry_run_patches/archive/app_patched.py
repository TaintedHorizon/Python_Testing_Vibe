# Dry-run patched snippet for doc_processor/app.py
# Purpose: ensure log_dir uses app_config or TEST_TMPDIR and is created safely
import os
import tempfile
try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.getenv('LOG_DIR') or os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()

# Example usage:
log_dir = getattr(__import__('doc_processor.config_manager', fromlist=['app_config']).app_config, 'LOG_DIR', None)
if not log_dir:
    log_dir = select_tmp_dir()
try:
    os.makedirs(log_dir, exist_ok=True)
except Exception:
    log_dir = os.getcwd()


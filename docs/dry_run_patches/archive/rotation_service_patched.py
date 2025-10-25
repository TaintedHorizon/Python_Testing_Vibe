# Dry-run patched snippet for doc_processor/services/rotation_service.py
# Purpose: ensure any temporary files created by rotation service are written to test-safe dirs
import os
import tempfile
try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.getenv('ROTATION_TEMP_DIR') or os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()

# Example usage: when creating temp files

temp_dir = os.environ.get('ROTATION_TEMP_DIR') or select_tmp_dir()
try:
    os.makedirs(temp_dir, exist_ok=True)
except Exception:
    pass

# Use temp_dir for intermediate file paths

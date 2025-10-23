"""
Dry-run wrapper for tools/sdcard_imager/SDCardImager.py

Sets test-safe log destination before importing the GUI module so tests/CI
don't write logs into the repository. Priority:
 1) existing SDCARD_IMAGER_LOG or LOG_FILE_PATH
 2) TEST_TMPDIR
 3) TMPDIR
 4) fallback to tempfile.gettempdir()

Re-exports: SDCardImager, LOG_FILE_PATH, log_message, log_exception
"""
from __future__ import annotations

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

# If tests/CI didn't set a log path, set it to a test-scoped file.
if not (os.environ.get('SDCARD_IMAGER_LOG') or os.environ.get('LOG_FILE_PATH')):
    candidate = os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or select_tmp_dir()
    os.environ['SDCARD_IMAGER_LOG'] = os.path.join(candidate, 'sd_card_imager_error.log')

# Now import the original module so it picks up the override at import time.
from tools.sdcard_imager.SDCardImager import SDCardImager, LOG_FILE_PATH, log_message, log_exception  # type: ignore

__all__ = ['SDCardImager', 'LOG_FILE_PATH', 'log_message', 'log_exception']

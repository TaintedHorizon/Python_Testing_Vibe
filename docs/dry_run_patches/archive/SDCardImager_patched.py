"""
Dry-run wrapper for tools/sdcard_imager/SDCardImager.py

This wrapper ensures the log file is redirected to a test-safe location (prefer existing env, then TEST_TMPDIR, then select_tmp_dir())
before importing the original module so its module-level LOG_FILE_PATH picks up the override.
"""
from __future__ import annotations

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

# Prefer explicit overrides; otherwise put logs under TEST_TMPDIR or select_tmp_dir()
candidate = os.environ.get('SDCARD_IMAGER_LOG') or os.environ.get('LOG_FILE_PATH')
if not candidate:
    candidate = os.environ.get('TEST_TMPDIR') or select_tmp_dir()

# Set both names so the module picks either env it checks
os.environ.setdefault('SDCARD_IMAGER_LOG', candidate)
os.environ.setdefault('LOG_FILE_PATH', candidate)

def get_SDCardImager():
    """Lazy import helper that returns the SDCardImager class from the original module.

    Use this to avoid import-time side-effects and static analysis warnings in non-Windows test environments.
    """
    from tools.sdcard_imager.SDCardImager import SDCardImager  # type: ignore
    return SDCardImager

__all__ = ['get_SDCardImager']
"""Dry-run patched copy of tools/sdcard_imager/SDCardImager.py
This copy prefers TEST_TMPDIR/select_tmp_dir for log file paths and is non-destructive (for review).
"""
import os
import sys
import threading
import traceback
import datetime
import time
import ctypes
import logging

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        import tempfile
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

# Determine log path with env override or test-safe fallback
_env_log = os.environ.get('SDCARD_IMAGER_LOG') or os.environ.get('LOG_FILE_PATH')
_test_tmp = os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR')
if _env_log:
    LOG_FILE_PATH = _env_log
elif _test_tmp:
    LOG_FILE_PATH = os.path.join(_test_tmp, 'sd_card_imager_error.log')
else:
    LOG_FILE_PATH = os.path.join(select_tmp_dir(), 'sd_card_imager_error.log')

os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)

def log_message(message, level="INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}\n"
    try:
        with open(LOG_FILE_PATH, "a") as log_f:
            log_f.write(log_entry)
    except Exception:
        print(log_entry)

def log_exception(exc_type, exc_value, exc_traceback):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    error_message = f"[{timestamp}] [ERROR] Unhandled Exception:\n"
    error_message += "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        with open(LOG_FILE_PATH, "a") as log_f:
            log_f.write(error_message)
    except Exception:
        print(error_message)

sys.excepthook = log_exception

def is_admin():
    try:
        is_user_admin = ctypes.windll.shell32.IsUserAnAdmin()
        log_message(f"IsUserAnAdmin() returned: {is_user_admin}", "DEBUG")
        return is_user_admin
    except Exception as e:
        log_message(f"Error checking admin status: {e}", "ERROR")
        return False

def main():
    # Non-GUI test-safe entrypoint that just writes an initialization log.
    log_message("SDCardImager (dry-run patched) initialized.", "INFO")

if __name__ == '__main__':
    main()
# Dry-run patched copy of tools/sdcard_imager/SDCardImager.py
# Purpose: demonstrate LOG_FILE_PATH resolution already applied earlier
import os
import tempfile
_env_log = os.environ.get('SDCARD_IMAGER_LOG') or os.environ.get('LOG_FILE_PATH')
_test_tmp = os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR')
if _env_log:
    LOG_FILE_PATH = _env_log
elif _test_tmp:
    LOG_FILE_PATH = os.path.join(_test_tmp, 'sd_card_imager_error.log')
else:
    LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sd_card_imager_error.log")

try:
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
except Exception:
    pass

# rest of file omitted for dry-run

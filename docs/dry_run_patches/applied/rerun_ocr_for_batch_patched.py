"""
Dry-run wrapper for doc_processor/dev_tools/rerun_ocr_for_batch.py

Sets `PROCESSED_DIR` and `LOG_FILE_PATH` to test-scoped locations before
importing to avoid writing logs or processed outputs into the repo during tests.
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
os.environ.setdefault('LOG_FILE_PATH', os.path.join(base, 'logs', 'rerun_ocr.log'))

from doc_processor.dev_tools.rerun_ocr_for_batch import main, rerun_ocr  # type: ignore

__all__ = ['main', 'rerun_ocr']

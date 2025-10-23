"""
Dry-run wrapper for `doc_processor/document_detector.py`.

Ensures normalization/cache directories are redirected to TEST_TMPDIR/select_tmp_dir
before importing to avoid writing into the repository tree during tests.
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

# Default normalized/cache dirs
os.environ.setdefault('NORMALIZED_DIR', os.path.join(base, 'normalized'))
os.environ.setdefault('INTAKE_DIR', os.path.join(base, 'intake'))
os.environ.setdefault('PROCESSED_DIR', os.path.join(base, 'processed'))

from doc_processor import document_detector as original  # type: ignore

__all__ = ['original']

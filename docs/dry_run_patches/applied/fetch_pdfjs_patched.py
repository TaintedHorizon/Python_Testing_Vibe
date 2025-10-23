"""
Dry-run wrapper for doc_processor/dev_tools/fetch_pdfjs.py

Sets `PDFJS_DEST` env var to a test-scoped static directory before importing so
downloads do not write into the repository's static dir during tests/CI.
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
os.environ.setdefault('PDFJS_DEST', os.path.join(base, 'static', 'pdfjs'))

from doc_processor.dev_tools.fetch_pdfjs import main  # type: ignore

__all__ = ['main']

"""
Dry-run wrapper for doc_processor/dev_tools/regenerate_ai_suggestions.py

Sets `PROCESSED_DIR` and `FILING_CABINET_DIR` to test-scoped locations before
importing to avoid writing suggestions or artifacts into the repo during tests.
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
os.environ.setdefault('FILING_CABINET_DIR', os.path.join(base, 'filing_cabinet'))

from doc_processor.dev_tools.regenerate_ai_suggestions import main, regenerate  # type: ignore

__all__ = ['main', 'regenerate']

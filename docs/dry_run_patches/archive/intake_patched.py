"""
Dry-run wrapper for `doc_processor/routes/intake.py`.

Sets `INTAKE_DIR`, `PROCESSED_DIR`, and `CACHE_DIR` to test-scoped locations before
importing so that blueprint import-time operations use safe directories during tests.
Re-exports the `bp` blueprint object for the application to import during test runs.
"""
from __future__ import annotations

import os
import tempfile
from typing import Any

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir() -> str:
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
os.makedirs(base, exist_ok=True)

# Test-safe defaults (only set if not already configured)
os.environ.setdefault('INTAKE_DIR', os.path.join(base, 'intake'))
os.environ.setdefault('PROCESSED_DIR', os.path.join(base, 'processed'))
os.environ.setdefault('CACHE_DIR', os.path.join(base, 'cache'))

# Import the original blueprint after environment is prepared
from doc_processor.routes.intake import bp as bp  # type: ignore

__all__ = ['bp']

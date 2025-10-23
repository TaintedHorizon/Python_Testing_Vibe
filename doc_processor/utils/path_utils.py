"""Path utilities for test-friendly temporary and export directory resolution.

Provides a single canonical implementation for selecting temporary
directories and resolving the filing cabinet/export locations with the
precedence used across the codebase:

  1. app_config setting (when present)
  2. explicit environment variable (EXPORT_DIR / FILING_CABINET_DIR)
  3. TEST_TMPDIR
  4. TMPDIR
  5. tempfile.gettempdir()
  6. os.getcwd() (last resort)

These helpers make it safe to run tests in CI by allowing tests to set
`TEST_TMPDIR` or configure `app_config` to a tmp path while preserving
production behavior when real paths are configured.
"""
from __future__ import annotations

import os
import tempfile
from typing import Optional

try:
    # app_config is available when running the app via package import
    from ..config_manager import app_config
except Exception:
    app_config = None  # type: ignore


def select_tmp_dir() -> str:
    """Select a temporary directory with test-friendly precedence.

    Precedence: TEST_TMPDIR -> TMPDIR -> system tempfile.gettempdir() -> cwd
    """
    try:
        return os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()
    except Exception:
        return os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or os.getcwd()


def ensure_dir(path: str) -> str:
    """Ensure directory exists (best-effort). Returns absolute path.

    If creation fails, returns the original absolute path (caller may
    choose to fallback further).
    """
    abspath = os.path.abspath(path)
    try:
        os.makedirs(abspath, exist_ok=True)
    except Exception:
        # If we cannot create, just return the absolute path; callers
        # should handle fallbacks where appropriate.
        return abspath
    return abspath


def resolve_filing_cabinet_dir(category: Optional[str] = None) -> str:
    """Resolve a safe filing cabinet directory for exports/sidecars.

    Precedence: app_config.FILING_CABINET_DIR -> FILING_CABINET_DIR env -> TEST_TMPDIR -> TMPDIR -> system tempdir -> cwd
    If category is provided, returns the category subdirectory (sanitized with spaces replaced by '_') and ensures it exists.
    """
    base = None
    try:
        if app_config is not None:
            base = getattr(app_config, 'FILING_CABINET_DIR', None)
    except Exception:
        base = None

    base = base or os.environ.get('FILING_CABINET_DIR') or os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()

    if category:
        safe_category = category.replace(' ', '_')
        path = os.path.join(base, safe_category)
    else:
        path = base

    return ensure_dir(path)

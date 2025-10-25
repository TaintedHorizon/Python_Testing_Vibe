"""
Dry-run wrapper for `doc_processor.dev_tools.reset_environment`.

Sets processed dir to a test-safe path before delegating.
"""
import os

from doc_processor.utils.path_utils import select_tmp_dir


def ensure_env_var_from_test(var_name: str, fallback_subdir: str | None = None) -> str:
    if var_name in os.environ and os.environ.get(var_name):
        return os.environ[var_name]
    base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
    if fallback_subdir:
        path = os.path.join(base, fallback_subdir)
    else:
        path = os.path.join(base, "devtools")
    os.environ.setdefault(var_name, path)
    return os.environ[var_name]


ensure_env_var_from_test("PROCESSED_DIR", "processed")


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.reset_environment")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for doc_processor/dev_tools/reset_environment.py

Sets `PROCESSED_DIR` and `FILING_CABINET_DIR` to test-scoped locations before
importing to avoid clearing real data during tests.
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

from doc_processor.dev_tools.reset_environment import main, clear_environment  # type: ignore

__all__ = ['main', 'clear_environment']
# Dry-run patched copy of doc_processor/dev_tools/reset_environment.py
# Purpose: ensure CATEGORIES_BACKUP_DIR defaults to test-safe location but honors env override
import os
import tempfile
CATEGORIES_BACKUP_DIR = os.environ.get('CATEGORIES_BACKUP_DIR') or os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()
CATEGORIES_BACKUP_FILE = os.path.join(CATEGORIES_BACKUP_DIR, "custom_categories_backup.json")

# rest of logic unchanged for dry-run

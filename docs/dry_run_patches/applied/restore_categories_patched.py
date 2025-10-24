"""
Dry-run wrapper for `doc_processor.dev_tools.restore_categories`.
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


ensure_env_var_from_test("CATEGORIES_BACKUP_DIR", "categories_backups")


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.restore_categories")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for `doc_processor/dev_tools/restore_categories.py`.

This sets `CATEGORIES_BACKUP_DIR` to a TEST_TMPDIR-scoped location before importing
so backups/read/write use a safe directory during tests.
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

os.environ.setdefault('CATEGORIES_BACKUP_DIR', os.path.join(base, 'dev_tool_backups'))

from doc_processor.dev_tools.restore_categories import main  # type: ignore

__all__ = ['main']

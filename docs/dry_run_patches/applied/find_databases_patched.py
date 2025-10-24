"""
Dry-run wrapper for `doc_processor.dev_tools.find_databases`.

Ensures DB search/backup locations are test-scoped and delegates.
"""
import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir, ensure_dir
except Exception:
    def select_tmp_dir() -> str:
        return os.environ.get("TEST_TMPDIR") or os.environ.get("TMPDIR") or tempfile.gettempdir()

    def ensure_dir(p: str) -> None:
        os.makedirs(p, exist_ok=True)


base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
ensure_dir(base)

os.environ.setdefault("DB_SEARCH_DIR", base)
os.environ.setdefault("DB_BACKUP_DIR", os.path.join(base, "db_backups"))


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.find_databases")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for `doc_processor.dev_tools.find_databases`.

Ensures any search/copy paths point inside a TEST_TMPDIR-local area to avoid
enumerating or copying production DB files during tests.
"""

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir() -> str:
        return os.environ.get("TEST_TMPDIR") or os.environ.get("TMPDIR") or tempfile.gettempdir()

base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
os.makedirs(base, exist_ok=True)

os.environ.setdefault("DB_SEARCH_BASE", os.path.join(base, "db_search"))
os.environ.setdefault("DB_BACKUP_DIR", os.path.join(base, "db_backups"))

def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.find_databases")
    if hasattr(mod, "main"):
        result = mod.main()
        return int(result or 0)
    if hasattr(mod, "run"):
        result = mod.run()
        return int(result or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for `doc_processor.dev_tools.find_databases`.

This wrapper ensures any scanning artifacts or backups remain under TEST_TMPDIR.
"""
import os

from doc_processor.utils.path_utils import select_tmp_dir


def ensure_env_var_from_test(var_name: str, fallback_subdir: str | None = None) -> str:
    if var_name in os.environ and os.environ.get(var_name):
        return os.environ[var_name]
    base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
    path = os.path.join(base, fallback_subdir or "devtools")
    os.environ.setdefault(var_name, path)
    return os.environ[var_name]


ensure_env_var_from_test("DB_SCAN_OUTPUT_DIR", "db_scan")


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.find_databases")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for dev_tools/find_databases.py

Ensures `DB_BACKUP_DIR` is set to a safe test-scoped directory before importing
the original module.
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
os.environ.setdefault('DB_BACKUP_DIR', os.path.join(base, 'db_backups'))

from dev_tools.find_databases import main, find_databases  # type: ignore

__all__ = ['main', 'find_databases']

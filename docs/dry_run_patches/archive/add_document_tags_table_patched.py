"""
Dry-run wrapper for `doc_processor.dev_tools.add_document_tags_table`.

Sets a safe backup/DB dir for tests then delegates to the original module.
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


ensure_env_var_from_test("DB_BACKUP_DIR", "db_backups")


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.add_document_tags_table")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for doc_processor/dev_tools/add_document_tags_table.py

Sets `DATABASE_PATH` and `DB_BACKUP_DIR` to test-scoped locations (prefer
`TEST_TMPDIR`) before importing the original script to avoid touching real DBs.
"""
from __future__ import annotations

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir, ensure_dir
except Exception:
    def select_tmp_dir():
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()
    def ensure_dir(p: str):
        os.makedirs(p, exist_ok=True)

base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
ensure_dir(base)

# Prefer explicit DATABASE_PATH if the user set it, otherwise route to test tmp
if 'DATABASE_PATH' not in os.environ:
    os.environ['DATABASE_PATH'] = os.path.join(base, 'documents_test.db')

os.environ.setdefault('DB_BACKUP_DIR', os.path.join(base, 'db_backups'))

from doc_processor.dev_tools.add_document_tags_table import main, upgrade_database  # type: ignore

__all__ = ['main', 'upgrade_database']

"""
Dry-run wrapper for `doc_processor/routes/batch.py`.

Sets test-safe defaults and imports the original module. Non-invasive: uses
`os.environ.setdefault` so explicit environment settings are preserved.
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

# Ensure cache and temp locations used by batch routes are test-scoped
os.environ.setdefault("BATCH_TEMP_DIR", os.path.join(base, "batch_temp"))
os.environ.setdefault("BATCH_BACKUP_DIR", os.path.join(base, "batch_backups"))

# Import the original routes module so tests can import this wrapper instead
from doc_processor.routes.batch import *  # noqa: F401,F403

__all__ = [name for name in dir() if not name.startswith("_")]

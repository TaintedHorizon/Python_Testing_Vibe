"""
Dry-run wrapper for `doc_processor/routes/manipulation.py`.

Redirects file/rotation cache paths to TEST_TMPDIR and imports the original module.
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

os.environ.setdefault("ROTATION_CACHE_DIR", os.path.join(base, "rotation_cache"))
os.environ.setdefault("MANIPULATION_TEMP_DIR", os.path.join(base, "manipulation_temp"))

from doc_processor.routes.manipulation import *  # noqa: F401,F403

__all__ = [name for name in dir() if not name.startswith("_")]

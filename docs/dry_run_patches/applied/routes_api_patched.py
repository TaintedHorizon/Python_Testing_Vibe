"""
Dry-run wrapper for `doc_processor/routes/api.py`.

Provides test-scoped artifacts and temp dirs, then delegates to the original module.
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

os.environ.setdefault("API_ARTIFACTS_DIR", os.path.join(base, "api_artifacts"))

from doc_processor.routes.api import *  # noqa: F401,F403

__all__ = [name for name in dir() if not name.startswith("_")]

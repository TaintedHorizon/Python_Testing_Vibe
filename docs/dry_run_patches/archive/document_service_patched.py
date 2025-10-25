"""
Non-invasive wrapper for `doc_processor/services/document_service.py`.

Sets test DB and temp locations to TEST_TMPDIR when not explicitly provided, then
imports the original service so tests can import the wrapper safely.
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

# Ensure an isolated test database location unless explicitly set
os.environ.setdefault("DATABASE_PATH", os.path.join(base, "documents.db"))
os.environ.setdefault("INTAKE_DIR", os.path.join(base, "intake"))
os.environ.setdefault("PROCESSED_DIR", os.path.join(base, "processed"))

from doc_processor.services.document_service import *  # noqa: F401,F403

__all__ = [name for name in dir() if not name.startswith("_")]

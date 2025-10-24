"""
Dry-run wrapper for `doc_processor.dev_tools.fetch_pdfjs`.

Redirects downloaded/static assets into TEST_TMPDIR and delegates to original.
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
static_test_dir = os.path.join(base, "static")
ensure_dir(static_test_dir)

# If the project expects FETCH_PDFJS_DIR or STATIC_DIR, prefer TEST_TMPDIR
os.environ.setdefault("FETCH_PDFJS_DIR", static_test_dir)
os.environ.setdefault("STATIC_DIR", static_test_dir)


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.fetch_pdfjs")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for `doc_processor.dev_tools.fetch_pdfjs`.

Sets PDFJS/DOWNLOAD paths to test-scoped locations (prefer `TEST_TMPDIR`) so
asset downloads during tests don't alter repository state.
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

os.environ.setdefault("PDFJS_DIR", os.path.join(base, "static", "pdfjs"))
os.environ.setdefault("DOWNLOADS_DIR", os.path.join(base, "downloads"))

def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.fetch_pdfjs")
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
Dry-run wrapper for doc_processor/dev_tools/fetch_pdfjs.py

Sets `PDFJS_DEST` env var to a test-scoped static directory before importing so
downloads do not write into the repository's static dir during tests/CI.
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
os.environ.setdefault('PDFJS_DEST', os.path.join(base, 'static', 'pdfjs'))

from doc_processor.dev_tools.fetch_pdfjs import main  # type: ignore

__all__ = ['main']

"""
Dry-run wrapper for `tools.download_manager.download_manager_gui`.

Sets GUI download directories to TEST_TMPDIR and delegates.
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
gui_download_dir = os.path.join(base, "gui_downloads")
ensure_dir(gui_download_dir)

os.environ.setdefault("GUI_DOWNLOADS_DIR", gui_download_dir)


def _main() -> int:
    from importlib import import_module

    mod = import_module("tools.download_manager.download_manager_gui")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for tools/download_manager/download_manager_gui.py

Ensures GUI download functions default to TEST_TMPDIR/select_tmp_dir when no
download_dir is provided to avoid writing into repo during test runs.
"""
from __future__ import annotations

import os
import tempfile
from typing import Optional

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

os.environ.setdefault('DOWNLOAD_DIR', os.path.join(os.environ.get('TEST_TMPDIR') or select_tmp_dir(), 'downloads'))

from tools.download_manager.download_manager_gui import download_files_from_url as _download_gui  # type: ignore
from typing import Any


def download_files_from_url(url: str, download_dir: Optional[str] = None, *args: Any, **kwargs: Any):
    # Guarantee a non-None str value for the wrapped call so static checkers are happy
    download_dir = (
        download_dir
        or os.environ.get('DOWNLOAD_DIR')
        or select_tmp_dir()
    )
    return _download_gui(url, download_dir, *args, **kwargs)

__all__ = ['download_files_from_url']

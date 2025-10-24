"""
Dry-run wrapper for `tools.download_manager.download_manager`.

Ensures downloads go into TEST_TMPDIR and delegates to the original module.
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
download_dir = os.path.join(base, "downloads")
ensure_dir(download_dir)

os.environ.setdefault("DOWNLOADS_DIR", download_dir)


def _main() -> int:
    from importlib import import_module

    mod = import_module("tools.download_manager.download_manager")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for tools/download_manager/download_manager.py

Provides a safe helper `download_files_from_url_safe` that defaults to a test-scoped
directory (select_tmp_dir()) when `download_dir` is omitted. Re-exports the original
`download_files_from_url` for callers that want the raw function.
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

from tools.download_manager.download_manager import download_files_from_url  # type: ignore

def download_files_from_url_safe(url: str, download_dir: Optional[str] = None, **kwargs):
    """Call the original downloader but default the destination to a test-safe dir.

    Args:
        url: remote directory URL
        download_dir: optional local path. If None, use select_tmp_dir().
        kwargs: passed to original function (max_retries, retry_delay)
    """
    if not download_dir:
        download_dir = select_tmp_dir()
    return download_files_from_url(url, download_dir, **kwargs)

__all__ = ['download_files_from_url', 'download_files_from_url_safe']

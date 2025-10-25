"""
Dry-run wrapper for `tools/file_utils/file_copy_regex.py`.

Routes any copy targets to TEST_TMPDIR and delegates to the original module.
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

# Default destination for copy operations when not explicitly provided
os.environ.setdefault("FILE_COPY_DEST", os.path.join(base, "file_copy_dest"))


def _main() -> int:
    from importlib import import_module

    mod = import_module("tools.file_utils.file_copy_regex")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for tools/file_utils/file_copy_regex.py

Purpose: ensure the script writes to a test-safe destination during CI/tests by setting
the FILE_UTILS_DEST environment variable if it's not already provided. Precedence:
 1) existing FILE_UTILS_DEST env
 2) TEST_TMPDIR env
 3) TMPDIR env
 4) doc_processor.utils.path_utils.select_tmp_dir()

This wrapper then imports and re-exports the original module's public API (main, find_matching_files)
so tests can import this module instead of the original when running in dry-run/test mode.
"""
from __future__ import annotations

import os
import tempfile

try:
    # prefer the project's central helper when available
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    # fallback minimal chooser
    def select_tmp_dir():
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

# If tests/CI didn't already set a destination, set FILE_UTILS_DEST to a safe test-scoped path.
if 'FILE_UTILS_DEST' not in os.environ:
    # prefer explicit TEST_TMPDIR/TMPDIR if provided by the CI environment
    candidate = os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR')
    if candidate:
        os.environ['FILE_UTILS_DEST'] = candidate
    else:
        # last-resort: use the project's select_tmp_dir() helper
        os.environ['FILE_UTILS_DEST'] = select_tmp_dir()

# Import the original module after setting the environment so it picks up the override.
from tools.file_utils.file_copy_regex import main, find_matching_files  # type: ignore

__all__ = ['main', 'find_matching_files']

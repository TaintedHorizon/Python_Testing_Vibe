"""
Dry-run wrapper for `doc_processor.dev_tools.cleanup_filing_cabinet_names`.
"""
import os

from doc_processor.utils.path_utils import select_tmp_dir


def ensure_env_var_from_test(var_name: str, fallback_subdir: str | None = None) -> str:
    if var_name in os.environ and os.environ.get(var_name):
        return os.environ[var_name]
    base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
    if fallback_subdir:
        path = os.path.join(base, fallback_subdir)
    else:
        path = os.path.join(base, "devtools")
    os.environ.setdefault(var_name, path)
    return os.environ[var_name]


# Ensure filing cabinet path and a backup base are safe
ensure_env_var_from_test("FILING_CABINET_DIR", "filing_cabinet")
ensure_env_var_from_test("DEV_TOOL_BACKUP_DIR", "devtool_backups")


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.cleanup_filing_cabinet_names")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for `doc_processor/dev_tools/cleanup_filing_cabinet_names.py`.

Sets test-scoped filing cabinet path and re-exports main function.
"""
import os
from pathlib import Path

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        import tempfile
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
Path(base).mkdir(parents=True, exist_ok=True)

os.environ.setdefault('FILING_CABINET_DIR', str(Path(base) / 'filing_cabinet'))
os.environ.setdefault('LOG_FILE_PATH', str(Path(base) / 'cleanup_filing_cabinet_names.log'))

try:
    from doc_processor.dev_tools import cleanup_filing_cabinet_names as _original  # type: ignore
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'dev_tools' / 'cleanup_filing_cabinet_names.py'
    spec = importlib.util.spec_from_file_location('cleanup_filing_cabinet_names', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load cleanup_filing_cabinet_names module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []
_tmp = getattr(_original, 'main', None)
if _tmp is not None:
    main = _tmp
    __all__.append('main')
"""
Dry-run wrapper for doc_processor/dev_tools/cleanup_filing_cabinet_names.py

Sets `FILING_CABINET_CLEANUP_DIR` and `FILING_CABINET_DIR` to test-safe locations
before importing so backups and logs are written under TEST_TMPDIR during tests.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
os.makedirs(base, exist_ok=True)

# set default filing cabinet directory to a per-test folder if not already configured
os.environ.setdefault('FILING_CABINET_DIR', os.path.join(base, 'filing_cabinet'))
os.environ.setdefault('FILING_CABINET_CLEANUP_DIR', os.path.join(base, 'filing_cleanup'))

from doc_processor.dev_tools.cleanup_filing_cabinet_names import FilingCabinetCleanup, main  # type: ignore

__all__ = ['FilingCabinetCleanup', 'main']
"""
Dry-run patched wrapper for `doc_processor/dev_tools/cleanup_filing_cabinet_names.py`.

Redirects backups/logs to TEST-safe locations and exposes the main class for dry-run testing.
"""
import os

from doc_processor.dev_tools import cleanup_filing_cabinet_names as _orig
try:
    from doc_processor.utils.path_utils import select_tmp_dir, ensure_dir
except Exception:
    from utils.path_utils import select_tmp_dir, ensure_dir  # type: ignore


def _apply_test_safe_overrides():
    # Prefer explicit override env var FILING_CABINET_CLEANUP_DIR, else use select_tmp_dir
    cleanup_base = os.environ.get('FILING_CABINET_CLEANUP_DIR') or select_tmp_dir()
    try:
        ensure_dir(cleanup_base)
    except Exception:
        os.makedirs(cleanup_base, exist_ok=True)
    os.environ['FILING_CABINET_CLEANUP_DIR'] = cleanup_base


_apply_test_safe_overrides()

# Expose the class for tests to instantiate
FilingCabinetCleanup = _orig.FilingCabinetCleanup

__all__ = ['FilingCabinetCleanup']
# Dry-run patched copy of doc_processor/dev_tools/cleanup_filing_cabinet_names.py
# Purpose: ensure backup_dir and log_file default to test-safe locations and honor env overrides
import os
import tempfile
try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.environ.get('FILING_CABINET_CLEANUP_DIR') or os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()

# In __init__, replace cleanup_base resolution with:
# cleanup_base = os.environ.get('FILING_CABINET_CLEANUP_DIR') or select_tmp_dir()
# This ensures backups/logs default to a test-scoped area and avoid writing into the filing cabinet during tests.

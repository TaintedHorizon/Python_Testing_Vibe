"""
Dry-run wrapper for `dev_tools/cleanup_test_artifacts.py` at repository root.

This wrapper redirects artifact output to TEST_TMPDIR.
"""
import os
from doc_processor.utils.path_utils import select_tmp_dir


def ensure_env_var_from_test(var_name: str, fallback_subdir: str | None = None) -> str:
    if var_name in os.environ and os.environ.get(var_name):
        return os.environ[var_name]
    base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
    path = os.path.join(base, fallback_subdir or "dev_tools_artifacts")
    os.environ.setdefault(var_name, path)
    return os.environ[var_name]


ensure_env_var_from_test("CLEANUP_TEST_ARTIFACTS_DIR", "cleanup_test_artifacts")


def _main() -> int:
    from importlib import import_module

    # top-level dev_tools module lives at dev_tools.cleanup_test_artifacts
    mod = import_module("dev_tools.cleanup_test_artifacts")
    if hasattr(mod, "main"):
        return mod.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for `doc_processor/dev_tools/cleanup_test_artifacts.py`.

Sets test-scoped directories before importing and re-exports main/cleanup functions.
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

os.environ.setdefault('PROCESSED_DIR', str(Path(base) / 'processed'))
os.environ.setdefault('FILING_CABINET_DIR', str(Path(base) / 'filing_cabinet'))
os.environ.setdefault('LOG_FILE_PATH', str(Path(base) / 'cleanup_test_artifacts.log'))

try:
    # static analyzer may not resolve dev_tools submodules
    from doc_processor.dev_tools import cleanup_test_artifacts as _original  # type: ignore
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'dev_tools' / 'cleanup_test_artifacts.py'
    spec = importlib.util.spec_from_file_location('cleanup_test_artifacts', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load cleanup_test_artifacts module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []
_tmp = getattr(_original, 'main', None)
if _tmp is not None:
    main = _tmp
    __all__.append('main')
_tmp = getattr(_original, 'cleanup', None)
if _tmp is not None:
    cleanup = _tmp
    __all__.append('cleanup')
"""
Dry-run wrapper for dev_tools/cleanup_test_artifacts.py

Ensures DB_BACKUP_DIR is set to a test-scoped path before importing the module so
the tool does not operate on repository-local backup folders during tests.
"""
from __future__ import annotations

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

# Ensure TEST_TMPDIR exists and DB_BACKUP_DIR is overridden for tests
base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
os.makedirs(base, exist_ok=True)
os.environ.setdefault('DB_BACKUP_DIR', os.path.join(base, 'db_backups'))

from dev_tools.cleanup_test_artifacts import main  # type: ignore

__all__ = ['main']

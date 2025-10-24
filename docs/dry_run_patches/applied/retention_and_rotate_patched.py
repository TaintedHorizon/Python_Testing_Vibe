"""
Dry-run wrapper for `dev_tools/retention_and_rotate.py` at repository root.

Redirects archive destination to TEST_TMPDIR for tests.
"""
import os
from doc_processor.utils.path_utils import select_tmp_dir


def ensure_env_var_from_test(var_name: str, fallback_subdir: str | None = None) -> str:
    if var_name in os.environ and os.environ.get(var_name):
        return os.environ[var_name]
    base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
    path = os.path.join(base, fallback_subdir or "retention_archives")
    os.environ.setdefault(var_name, path)
    return os.environ[var_name]


ensure_env_var_from_test("RETENTION_ARCHIVE_DIR", "retention_archives")


def _main() -> int:
    from importlib import import_module

    mod = import_module("dev_tools.retention_and_rotate")
    if hasattr(mod, "main"):
        return mod.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for `doc_processor/dev_tools/retention_and_rotate.py`.

Sets test-scoped environment variables to ensure backups/rotations happen under TEST_TMPDIR.
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
os.environ.setdefault('DB_BACKUP_DIR', str(Path(base) / 'db_backups'))
os.environ.setdefault('LOG_FILE_PATH', str(Path(base) / 'retention.log'))

try:
    # static analyzer may not resolve dev_tools submodules here
    from doc_processor.dev_tools import retention_and_rotate as _original  # type: ignore
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'dev_tools' / 'retention_and_rotate.py'
    spec = importlib.util.spec_from_file_location('retention_and_rotate', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load retention_and_rotate module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []
_tmp = getattr(_original, 'main', None)
if _tmp is not None:
    main = _tmp
    __all__.append('main')
_tmp = getattr(_original, 'run', None)
if _tmp is not None:
    run = _tmp
    __all__.append('run')
from __future__ import annotations
"""
Dry-run wrapper for dev_tools/retention_and_rotate.py

Sets DB_BACKUP_DIR and LOG_FILE_PATH/LOG_DIR to a test-scoped directory (TEST_TMPDIR or select_tmp_dir)
before importing so the module operates on temporary paths during tests.
"""

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

# Determine a test-safe base directory
base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
os.makedirs(base, exist_ok=True)

# Set backup and log dirs if not explicitly provided
os.environ.setdefault('DB_BACKUP_DIR', os.path.join(base, 'db_backups'))
os.environ.setdefault('LOG_FILE_PATH', os.path.join(base, 'logs', 'retention_and_rotate.log'))

# Import target module after setting env
from dev_tools.retention_and_rotate import main, load_env  # type: ignore

__all__ = ['main', 'load_env']
"""
Dry-run wrapper for dev_tools/retention_and_rotate.py

Sets DB_BACKUP_DIR and LOG_FILE_PATH/TEST_TMPDIR-based LOG_DIR to test-scoped locations
so CI/tests don't mutate repo backups or logs. Then imports and re-exports `main`.
"""
from __future__ import annotations

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

# Ensure TEST_TMPDIR exists
if 'TEST_TMPDIR' not in os.environ:
    base = select_tmp_dir()
    os.environ['TEST_TMPDIR'] = base

# Provide safe DB backup dir and log path if not already set
os.environ.setdefault('DB_BACKUP_DIR', os.path.join(os.environ['TEST_TMPDIR'], 'db_backups'))
os.environ.setdefault('LOG_FILE_PATH', os.path.join(os.environ['TEST_TMPDIR'], 'logs', 'app.log'))

# Import the original module after envs set.
from dev_tools.retention_and_rotate import main  # type: ignore

__all__ = ['main']

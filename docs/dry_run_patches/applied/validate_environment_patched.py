"""
Dry-run wrapper for `doc_processor.dev_tools.validate_environment`.

Sets safe temp locations and delegates to the original module. This wrapper is
intended to make CI/test runs safe by avoiding writes to user-local paths.
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

# Provide conservative defaults for various envs used by validation
os.environ.setdefault("INTAKE_DIR", os.path.join(base, "intake"))
os.environ.setdefault("PROCESSED_DIR", os.path.join(base, "processed"))
os.environ.setdefault("DB_BACKUP_DIR", os.path.join(base, "db_backups"))


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.validate_environment")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for `doc_processor.dev_tools.validate_environment`.

Sets logging and temp directories to test-scoped locations to avoid altering
local developer environments during CI runs.
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

os.environ.setdefault("LOG_FILE_PATH", os.path.join(base, "logs", "validate_environment.log"))
os.environ.setdefault("TEMP_DIR", os.path.join(base, "tmp"))

def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.validate_environment")
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
Dry-run wrapper for `doc_processor/dev_tools/validate_environment.py`.

Sets a TEST_TMPDIR scoped place for any temporary artifacts and re-exports validators.
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

os.environ.setdefault('LOG_FILE_PATH', str(Path(base) / 'validate_environment.log'))
os.environ.setdefault('TEMP_DIR', str(Path(base) / 'validate_tmp'))

try:
    from doc_processor.dev_tools import validate_environment as _original  # type: ignore
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'dev_tools' / 'validate_environment.py'
    spec = importlib.util.spec_from_file_location('validate_environment', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load validate_environment module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []
_tmp = getattr(_original, 'main', None)
if _tmp is not None:
    main = _tmp
    __all__.append('main')
_tmp = getattr(_original, 'validate', None)
if _tmp is not None:
    validate = _tmp
    __all__.append('validate')

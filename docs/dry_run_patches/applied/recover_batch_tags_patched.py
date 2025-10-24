"""
Dry-run wrapper for `doc_processor.dev_tools.recover_batch_tags`.
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


# Ensure filing cabinet base is safe for tests
ensure_env_var_from_test("FILING_CABINET_DIR", "filing_cabinet")


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.recover_batch_tags")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for `doc_processor/dev_tools/recover_batch_tags.py`.

Sets test-scoped DB and processed directories before importing and re-exports recover functions.
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

os.environ.setdefault('DATABASE_PATH', str(Path(base) / 'documents.db'))
os.environ.setdefault('DB_BACKUP_DIR', str(Path(base) / 'db_backups'))
os.environ.setdefault('PROCESSED_DIR', str(Path(base) / 'processed'))

try:
    from doc_processor.dev_tools import recover_batch_tags as _original  # type: ignore
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'dev_tools' / 'recover_batch_tags.py'
    spec = importlib.util.spec_from_file_location('recover_batch_tags', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load recover_batch_tags module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []
_tmp = getattr(_original, 'main', None)
if _tmp is not None:
    main = _tmp
    __all__.append('main')
_tmp = getattr(_original, 'recover_tags', None)
if _tmp is not None:
    recover_tags = _tmp
    __all__.append('recover_tags')
"""
Dry-run wrapper for doc_processor/dev_tools/recover_batch_tags.py

Sets `FILING_CABINET_DIR` to a test-scoped directory (TEST_TMPDIR/select_tmp_dir)
before importing so regenerated markdown writes into a safe location during tests.
"""
from __future__ import annotations

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

# Ensure a stable test tmp and set filing cabinet dir if not configured
base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
os.makedirs(base, exist_ok=True)
os.environ.setdefault('FILING_CABINET_DIR', os.path.join(base, 'filing_cabinet'))

from doc_processor.dev_tools.recover_batch_tags import main, regenerate_markdown  # type: ignore

__all__ = ['main', 'regenerate_markdown']

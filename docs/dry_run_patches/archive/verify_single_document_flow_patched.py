"""
Dry-run wrapper for `doc_processor.dev_tools.verify_single_document_flow`.

Sets processed and filing locations to safe TEST_TMPDIR locations then delegates.
"""
import os

from doc_processor.utils.path_utils import select_tmp_dir


def ensure_env_var_from_test(var_name: str, fallback_subdir: str | None = None) -> str:
    if var_name in os.environ and os.environ.get(var_name):
        return os.environ[var_name]
    base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
    path = os.path.join(base, fallback_subdir or "devtools")
    os.environ.setdefault(var_name, path)
    return os.environ[var_name]


ensure_env_var_from_test("PROCESSED_DIR", "processed")
ensure_env_var_from_test("FILING_CABINET_DIR", "filing_cabinet")


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.verify_single_document_flow")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for `doc_processor/dev_tools/verify_single_document_flow.py`.

Sets test-scoped directories and re-exports verification functions for safe test runs.
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
os.environ.setdefault('LOG_FILE_PATH', str(Path(base) / 'verify_single_document_flow.log'))

try:
    from doc_processor.dev_tools import verify_single_document_flow as _original  # type: ignore
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'dev_tools' / 'verify_single_document_flow.py'
    spec = importlib.util.spec_from_file_location('verify_single_document_flow', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load verify_single_document_flow module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []
_tmp = getattr(_original, 'main', None)
if _tmp is not None:
    main = _tmp
    __all__.append('main')
_tmp = getattr(_original, 'verify', None)
if _tmp is not None:
    verify = _tmp
    __all__.append('verify')

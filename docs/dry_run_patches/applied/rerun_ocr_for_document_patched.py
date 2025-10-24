"""
Dry-run wrapper for `doc_processor.dev_tools.rerun_ocr_for_document`.

Ensures processed/output dirs are under TEST_TMPDIR for tests.
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
ensure_env_var_from_test("SEARCHABLE_DIR", "searchable")


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.rerun_ocr_for_document")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for `doc_processor/dev_tools/rerun_ocr_for_document.py`.

Sets test-scoped PROCESSED_DIR and LOG_FILE_PATH before importing and re-exports main/process functions.
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
os.environ.setdefault('LOG_FILE_PATH', str(Path(base) / 'rerun_ocr_for_document.log'))

try:
    from doc_processor.dev_tools import rerun_ocr_for_document as _original  # type: ignore
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    fallback = repo_root / 'doc_processor' / 'dev_tools' / 'rerun_ocr_for_document.py'
    spec = importlib.util.spec_from_file_location('rerun_ocr_for_document', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load rerun_ocr_for_document module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []
_tmp = getattr(_original, 'main', None)
if _tmp is not None:
    main = _tmp
    __all__.append('main')
_tmp = getattr(_original, 'process_document', None)
if _tmp is not None:
    process_document = _tmp
    __all__.append('process_document')

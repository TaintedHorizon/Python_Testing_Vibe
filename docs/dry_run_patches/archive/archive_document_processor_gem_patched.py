"""
Dry-run wrapper for `archive/Document_Scanner_Ollama_outdated/document_processor_gem.py`.

Routes file outputs to a test-scoped temporary directory and delegates to the original
module. Uses setdefault so it does not override explicit configuration.
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

os.environ.setdefault("ARCHIVE_OUTPUT_DIR", os.path.join(base, "archive_outputs"))
os.environ.setdefault("OCR_CACHE_DIR", os.path.join(base, "ocr_cache"))


def _main() -> int:
    from importlib import import_module

    mod = import_module("archive.Document_Scanner_Ollama_outdated.document_processor_gem")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

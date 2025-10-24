"""
Dry-run wrapper for `archive/legacy/Document_Scanner_Ollama_outdated/document_processor_gca.py`.

Redirects outputs to safe test-scoped directories and delegates to the original module.
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

os.environ.setdefault("LEGACY_ARCHIVE_OUT", os.path.join(base, "legacy_archive"))
os.environ.setdefault("LEGACY_OCR_CACHE", os.path.join(base, "legacy_ocr_cache"))


def _main() -> int:
    from importlib import import_module

    mod = import_module("archive.legacy.Document_Scanner_Ollama_outdated.document_processor_gca")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

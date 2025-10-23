"""
Dry-run wrapper for archive/Document_Scanner_Gemini_outdated/document_processor.py
Redirects legacy outputs to TEST_TMPDIR/select_tmp_dir during tests. Falls back to file-load if package import not available.
"""

import os
from pathlib import Path

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        import tempfile
        return tempfile.gettempdir()

base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
Path(base).mkdir(parents=True, exist_ok=True)

for k in (
    "ARCHIVE_DIR",
    "OUTPUT_DIR",
    "CACHE_DIR",
    "PROCESSED_DIR",
    "EXPORT_DIR",
    "FILING_CABINET_DIR",
    "LOG_FILE_PATH",
    "DOWNLOAD_DIR",
):
    os.environ.setdefault(k, str(Path(base) / k.lower()))

# Try a normal import first, then fall back to a file-based import which is resilient to non-package layout
try:
    from Document_Scanner_Gemini_outdated import document_processor as _original
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[4]
    # Try both archive/Document_Scanner_Gemini_outdated and archive/legacy/Document_Scanner_Gemini_outdated
    paths_to_try = [
        repo_root / "archive" / "Document_Scanner_Gemini_outdated" / "document_processor.py",
        repo_root / "archive" / "legacy" / "Document_Scanner_Gemini_outdated" / "document_processor.py",
    ]
    for candidate in paths_to_try:
        if candidate.exists():
            spec = importlib.util.spec_from_file_location("legacy_document_processor", str(candidate))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            _original = mod
            break
    else:
        raise

if hasattr(_original, "main"):
    main = _original.main
if hasattr(_original, "process_documents"):
    process_documents = _original.process_documents

__all__ = [name for name in ("main", "process_documents") if name in globals()]

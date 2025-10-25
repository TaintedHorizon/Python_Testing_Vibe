"""
Dry-run wrapper for `archive/legacy/Document_Scanner_Gemini_outdated/document_processor.py`.

Redirects any archive/output paths to TEST_TMPDIR before importing the legacy
document processor module so running it during tests won't modify repo files.
"""
from __future__ import annotations

import os
from pathlib import Path
import importlib

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        import tempfile
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
Path(base).mkdir(parents=True, exist_ok=True)

os.environ.setdefault('ARCHIVE_OUTPUT_DIR', str(Path(base) / 'archive_output'))
os.environ.setdefault('LOG_FILE_PATH', str(Path(base) / 'legacy_document_processor.log'))

# Attempt to import via package path first; otherwise load from archive path
try:
    # Not a package in main code; prefer file import
    raise ImportError
except Exception:
    import importlib.util
    repo_root = Path(__file__).resolve().parents[3]
    fallback = repo_root / 'archive' / 'legacy' / 'Document_Scanner_Gemini_outdated' / 'document_processor.py'
    spec = importlib.util.spec_from_file_location('legacy.document_processor', str(fallback))
    if spec is None or spec.loader is None:
        raise ImportError('Could not load legacy document_processor module spec for dry-run wrapper')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _original = mod

__all__ = []
for candidate in ('main','process','run'):
    if hasattr(_original, candidate):
        __all__.append(candidate)

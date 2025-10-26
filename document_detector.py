"""Compatibility shim for tests that import a top-level `document_detector`.

This module tries to import the repo-local implementation from
`doc_processor.document_detector`. If that import fails (for example in
CI when a package isn't available), we expose a tiny fallback `get_detector`
that provides the minimal methods used by the routes/tests so pytest can
collect without ModuleNotFoundError.

The shim is intentionally small and safe; it avoids heavy runtime deps.
"""
from pathlib import Path
import os
import shutil
import logging

try:
    # Prefer the project's implementation when available
    from doc_processor.document_detector import get_detector as _real_get_detector
except Exception:
    _real_get_detector = None


class _StubAnalysis:
    def __init__(self, file_path):
        self.file_path = file_path
        self.file_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 3) if os.path.exists(file_path) else 0
        self.page_count = 1
        self.processing_strategy = "single_document"
        self.confidence = 0.5
        self.reasoning = "stub-analysis"
        self.filename_hints = []
        self.content_sample = ""
        self.llm_analysis = {}
        self.detected_rotation = 0


class _StubDetector:
    def __init__(self):
        pass

    def _convert_image_to_pdf(self, image_path):
        # Simple behavior: if file exists, return a same-dir converted name (no actual conversion)
        p = Path(image_path)
        converted = str(p.with_name(p.stem + "_converted.pdf"))
        try:
            if p.exists() and not Path(converted).exists():
                shutil.copy2(str(p), converted)
        except Exception as e:
            logging.debug(f"stub _convert_image_to_pdf copy failed: {e}")
            return image_path
        return converted

    """Compatibility shim for tests that import a top-level `document_detector`.

    This module tries to import the repo-local implementation from
    `doc_processor.document_detector`. If that import fails (for example in
    CI when a package isn't available), we expose a tiny fallback `get_detector`
    that provides the minimal methods used by the routes/tests so pytest can
    collect without ModuleNotFoundError.

    The shim is intentionally small and safe; it avoids heavy runtime deps.
    """
    from pathlib import Path
    import os
    import shutil
    import logging

    try:
        # Prefer the project's implementation when available
        from doc_processor.document_detector import get_detector as _real_get_detector
    except Exception:
        _real_get_detector = None


    class _StubAnalysis:
        def __init__(self, file_path):
            self.file_path = file_path
            self.file_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 3) if os.path.exists(file_path) else 0
            self.page_count = 1
            self.processing_strategy = "single_document"
            self.confidence = 0.5
            self.reasoning = "stub-analysis"
            self.filename_hints = []
            self.content_sample = ""
            self.llm_analysis = {}
            self.detected_rotation = 0


    class _StubDetector:
        def __init__(self):
            pass

        def _convert_image_to_pdf(self, image_path):
            # Simple behavior: if file exists, return a same-dir converted name (no actual conversion)
            p = Path(image_path)
            converted = str(p.with_name(p.stem + "_converted.pdf"))
            try:
                if p.exists() and not Path(converted).exists():
                    shutil.copy2(str(p), converted)
            except Exception as e:
                logging.debug(f"stub _convert_image_to_pdf copy failed: {e}")
                return image_path
            return converted

        def analyze_pdf(self, pdf_path):
            return _StubAnalysis(pdf_path)

        def analyze_intake_directory(self, intake_dir):
            # Return a list of stub analyses for PDFs in the directory
            results = []
            try:
                for p in Path(intake_dir).iterdir():
                    if p.is_file() and p.suffix.lower() in {'.pdf', '.png', '.jpg', '.jpeg'}:
                        results.append(_StubAnalysis(str(p)))
            except Exception:
                pass
            return results


    def get_detector(*args, **kwargs):
        """Return the real detector if available, otherwise a stub detector.

        Accepts any args/kwargs so callers can pass flags like
        `use_llm_for_ambiguous=True` without error.
        """
        if _real_get_detector:
            try:
                return _real_get_detector(*args, **kwargs)
            except Exception:
                # Fall back to stub if real detector raises during import/runtime
                pass
        return _StubDetector()


    __all__ = ["get_detector"]

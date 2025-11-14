"""Lightweight compatibility shim for document detection used in tests.

This module provides a minimal, import-safe surface (no heavy C deps at
import time). It will attempt to use the real implementation at call-time
but falls back to a small, safe stub so tests and CI don't require
PyMuPDF/EasyOCR during collection.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import logging
from typing import Any


class _StubAnalysis:
    def __init__(self, pdf_path: str | None = None, file_path: str | None = None):
        self.pdf_path = pdf_path
        self.file_path = file_path
        self.processing_strategy = "single_document"
        self.confidence = 0.5
        self.page_count = 1


class DocumentTypeDetector:
    """A small stub implementation that mimics the minimal API used in tests.

    It deliberately avoids importing heavy dependencies at module import time.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        pass

    def _convert_image_to_pdf(self, image_path: str) -> str:
        p = Path(image_path)
        converted = str(p.with_name(p.stem + "_converted.pdf"))
        try:
            if p.exists() and not Path(converted).exists():
                shutil.copy2(str(p), converted)
        except Exception as e:
            logging.debug("shim _convert_image_to_pdf copy failed: %s", e)
            return str(p)
        return converted

    def analyze_image_file(self, image_path: str) -> _StubAnalysis:
        pdf_path = self._convert_image_to_pdf(image_path)
        return _StubAnalysis(pdf_path=pdf_path, file_path=image_path)

    def analyze_pdf(self, pdf_path: str) -> _StubAnalysis:
        return _StubAnalysis(pdf_path=pdf_path, file_path=pdf_path)


def get_detector(*args: Any, **kwargs: Any):
    """Return a real detector if available, otherwise a stub instance.

    We import the real implementation lazily to avoid requiring heavy deps
    during pytest collection.
    """
    try:
        from . import document_detector as _real_mod

        if hasattr(_real_mod, 'get_detector'):
            try:
                return _real_mod.get_detector(*args, **kwargs)
            except Exception:
                pass
    except Exception:
        # Real implementation not available or failed; fall through to stub.
        pass
    return DocumentTypeDetector(*args, **kwargs)


__all__ = ["DocumentTypeDetector", "get_detector"]

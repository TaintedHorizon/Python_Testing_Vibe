import os
from pathlib import Path

from doc_processor.app import create_app
from doc_processor.config_manager import app_config
from doc_processor.document_detector import DocumentAnalysis


class DummyDetector:
    def __init__(self, tmp_dir: str):
        self.tmp_dir = tmp_dir

    def _convert_image_to_pdf(self, image_path: str) -> str:
        # produce a deterministic converted pdf path
        stem = Path(image_path).stem
        out = os.path.join(self.tmp_dir, f"{stem}_converted.pdf")
        # ensure file exists so analyze step can open it if needed
        Path(out).write_text("%PDF-FAKE")
        return out

    def analyze_pdf(self, pdf_path: str) -> DocumentAnalysis:
        # Return a lightweight DocumentAnalysis object with required attrs
        return DocumentAnalysis(
            file_path=pdf_path,
            file_size_mb=0.1,
            page_count=1,
            processing_strategy='single_document',
            confidence=0.9,
            reasoning=['dummy'],
        )


def test_analyze_intake_progress_emits_pdf_counters(monkeypatch, tmp_path):
    # Prepare intake dir with 3 files (2 pdf + 1 image)
    intake = tmp_path / 'intake'
    intake.mkdir()
    (intake / 'a.pdf').write_text('%PDF-1')
    (intake / 'b.pdf').write_text('%PDF-2')
    # write a minimal 1x1 PNG so image-processing paths can open it
    # Try to create a tiny valid PNG using Pillow when available; fallback to base64 bytes
    try:
        from PIL import Image
        img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
        img.save(intake / 'c.png', format='PNG')
    except Exception:
        import base64
        png_b64 = b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII='
        png_bytes = base64.b64decode(png_b64)
        (intake / 'c.png').write_bytes(png_bytes)

    # Point config to temp intake
    monkeypatch.setattr(app_config, 'INTAKE_DIR', str(intake))

    # Monkeypatch the detector factory used by the route module to avoid heavy deps
    import doc_processor.routes.intake as intake_module

    dummy = DummyDetector(str(tmp_path))
    monkeypatch.setattr(intake_module, 'get_detector', lambda use_llm_for_ambiguous=True: dummy)

    app = create_app()
    client = app.test_client()

    resp = client.get('/api/analyze_intake_progress')
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)

    # Ensure at least one per-PDF payload includes pdf_progress/pdf_total
    assert 'pdf_progress' in text and 'pdf_total' in text, f"SSE payload missing pdf_progress/pdf_total:\n{text}"

    # Check pdf_total equals number of files (2 pdfs + 1 image -> 3 PDFs after conversion)
    assert '"pdf_total": 3' in text or "'pdf_total': 3" in text

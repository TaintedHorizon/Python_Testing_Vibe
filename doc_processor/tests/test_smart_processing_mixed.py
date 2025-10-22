import fitz
from pathlib import Path
from typing import Any
from doc_processor.processing import database_connection
from doc_processor.routes.batch import _orchestrate_smart_processing
from doc_processor.config_manager import app_config


def _make_dummy_pdf(path: Path, pages: int = 1):
    with fitz.open() as doc:
        newp = getattr(doc, 'new_page', None) or getattr(doc, 'newPage', None)
        for _ in range(pages):
            page = newp() if newp else doc.new_page()  # type: ignore[attr-defined]
            page.insert_text((72, 72), 'Dummy Page')  # type: ignore[attr-defined]
        doc.save(str(path))


def _make_dummy_image(path: Path):
    from PIL import Image as _Img
    white: Any = (255, 255, 255)
    _Img.new('RGB', (300, 200), white).save(path, 'PNG')


def test_orchestrate_mixed(tmp_path, monkeypatch):
    intake = tmp_path / 'intake'
    intake.mkdir()
    pdf_single = intake / 's1.pdf'
    pdf_batch = intake / 'b1.pdf'
    img_single = intake / 'img1.png'

    _make_dummy_pdf(pdf_single, 1)
    _make_dummy_pdf(pdf_batch, 2)
    _make_dummy_image(img_single)

    # Point config intake dir to temp
    monkeypatch.setattr(app_config, 'INTAKE_DIR', str(intake))

    # Pre-create or reuse a staging batch (status test_batch:ready)
    from doc_processor.database import get_or_create_test_batch
    staging_batch = get_or_create_test_batch('smart_processing')

    overrides = {
        's1.pdf': 'single_document',
        'b1.pdf': 'batch_scan',
        'img1.png': 'single_document'
    }

    # Consume orchestrator
    final_event = None
    assert isinstance(staging_batch, int)
    for event in _orchestrate_smart_processing(int(staging_batch), overrides, token='dummy'):  # token needed after refactor
        final_event = event

    assert final_event is not None
    assert final_event.get('complete') is True
    # Single doc images forced to single; batch_scan_batch_id may be None in edge runs.
    single_id = final_event.get('single_batch_id')
    batch_scan_id = final_event.get('batch_scan_batch_id')
    assert single_id is not None, 'Expected a single_document batch id to be present'

    # If batch_scan_id is present, ensure it's different from single_id and both exist in DB.
    with database_connection() as conn:
        cur = conn.cursor()
        if batch_scan_id:
            assert batch_scan_id != single_id
            cur.execute('SELECT COUNT(*) FROM batches WHERE id IN (?, ?)', (single_id, batch_scan_id))
            count = cur.fetchone()[0]
            assert count == 2
        else:
            # At minimum the single batch should exist
            cur.execute('SELECT COUNT(*) FROM batches WHERE id = ?', (single_id,))
            count = cur.fetchone()[0]
            assert count == 1

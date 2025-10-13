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

    # Pre-create a staging batch (status ready)
    with database_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO batches (status) VALUES ('ready')")
        staging_batch = cur.lastrowid
        conn.commit()

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
    # Single doc images forced to single, so we should have two batches
    assert final_event.get('single_batch_id')
    assert final_event.get('batch_scan_batch_id')
    assert final_event['single_batch_id'] != final_event['batch_scan_batch_id']

    # Basic DB sanity: batches exist
    with database_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM batches WHERE id IN (?, ?)', (
            final_event['single_batch_id'], final_event['batch_scan_batch_id']))
        count = cur.fetchone()[0]
    assert count == 2

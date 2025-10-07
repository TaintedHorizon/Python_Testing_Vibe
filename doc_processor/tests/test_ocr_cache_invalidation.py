import os, sqlite3, time, pytest
from pathlib import Path

# We explicitly disable FAST_TEST_MODE to exercise real OCR path, but we'll mock pytesseract
os.environ['FAST_TEST_MODE'] = '0'

from doc_processor.config_manager import AppConfig
import importlib
import doc_processor.config_manager as _cfg_mod
import doc_processor.processing as _proc_mod
# Reload config & rebind to ensure FAST_TEST_MODE false takes effect even if prior tests set it true
_cfg_mod.app_config = AppConfig.load_from_env()
_proc_mod.app_config = _cfg_mod.app_config

@pytest.fixture()
def setup_env(tmp_path, monkeypatch):
    intake = tmp_path / 'intake'; intake.mkdir()
    filing = tmp_path / 'filing_cabinet'; filing.mkdir()
    processed = tmp_path / 'processed'; processed.mkdir()
    db_path = tmp_path / 'cachetest.db'
    monkeypatch.setenv('DATABASE_PATH', str(db_path))
    monkeypatch.setenv('INTAKE_DIR', str(intake))
    monkeypatch.setenv('FILING_CABINET_DIR', str(filing))
    monkeypatch.setenv('PROCESSED_DIR', str(processed))
    monkeypatch.setenv('WIP_DIR', str(processed))
    monkeypatch.setenv('ENABLE_TAG_EXTRACTION', '0')
    monkeypatch.setenv('OCR_RENDER_SCALE', '1.0')  # keep small
    monkeypatch.setenv('OCR_OVERLAY_TEXT_LIMIT', '128')

    # Reload config
    _cfg_mod.app_config = AppConfig.load_from_env()

    # Build DB (include signature column)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE single_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_pdf_path TEXT,
        searchable_pdf_path TEXT,
        ocr_text TEXT,
        ocr_confidence_avg REAL,
        ocr_source_signature TEXT
    );
    """)
    conn.commit(); conn.close()

    # Create a valid one-page PDF using PyMuPDF so downstream rasterization works
    import fitz
    pdf1 = intake / 'sample.pdf'
    doc = fitz.open()
    # Use legacy/new API with pragma to satisfy runtime despite static analyzer
    if hasattr(doc, 'new_page'):
        doc.new_page()  # type: ignore[attr-defined]
    else:
        doc.newPage()  # type: ignore[attr-defined]
    doc.save(str(pdf1)); doc.close()

    return tmp_path, pdf1, db_path


@pytest.fixture(autouse=True)
def mock_pytesseract(monkeypatch):
    class DummyOutput:
        # minimal dict interface used
        def __init__(self):
            self.data = {
                'text': ['Lorem', 'ipsum', 'dolor'],
                'conf': ['90','88','92']
            }
        def get(self, k, default=None):
            return self.data.get(k, default)
    def fake_image_to_data(img, output_type=None):
        return DummyOutput().data
    monkeypatch.setattr('pytesseract.image_to_data', fake_image_to_data)


def test_ocr_cache_reuse_and_invalidation(setup_env):
    tmp_path, pdf_path, db_path = setup_env
    from doc_processor.processing import create_searchable_pdf

    # Insert initial row BEFORE first OCR so function can update it
    conn = sqlite3.connect(db_path); cur = conn.cursor()
    cur.execute("INSERT INTO single_documents(id, original_pdf_path) VALUES (1,?)", (str(pdf_path),))
    conn.commit(); conn.close()

    out1 = tmp_path / 'first.pdf'
    text1, conf1, status1 = create_searchable_pdf(str(pdf_path), str(out1), document_id=1)
    assert status1.startswith('success')

    # Second call should reuse cache (status contains 'cached')
    text2, conf2, status2 = create_searchable_pdf(str(pdf_path), str(tmp_path/'second.pdf'), document_id=1)
    assert 'cached' in status2.lower(), 'Expected cached OCR reuse'
    assert text2 == text1

    # Modify file (change size + mtime) to trigger signature mismatch
    time.sleep(1.1)  # ensure mtime granularity difference
    with open(pdf_path, 'ab') as f:
        f.write(b'Added content to change hash')

    text3, conf3, status3 = create_searchable_pdf(str(pdf_path), str(tmp_path/'third.pdf'), document_id=1)
    assert 'cached' not in status3.lower(), 'Cache should have been invalidated after file change'

import os, sqlite3, tempfile, shutil, json, pytest
from importlib import reload

def make_min_db(db_path, pdf_path):
    conn = sqlite3.connect(db_path)
    conn.executescript("""
    CREATE TABLE single_documents (
        id INTEGER PRIMARY KEY,
        original_filename TEXT,
        original_pdf_path TEXT,
        ocr_text TEXT,
        ocr_confidence_avg REAL,
        page_count INTEGER,
        batch_id INTEGER,
        ai_suggested_category TEXT,
        ai_suggested_filename TEXT,
        ai_confidence REAL,
        ai_summary TEXT
    );
    CREATE TABLE IF NOT EXISTS document_rotations (
        document_id INTEGER PRIMARY KEY,
        rotation INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.execute("INSERT INTO single_documents (id, original_filename, original_pdf_path, ocr_text, ocr_confidence_avg, page_count, batch_id, ai_suggested_category, ai_suggested_filename, ai_confidence, ai_summary) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (1, 'sample.pdf', pdf_path, 'Existing OCR text', 75.5, 1, 101, 'PrevCat', 'prev_file', 0.88, 'Previous summary'))
    conn.commit(); conn.close()

def sample_pdf_bytes():
    return (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R>>endobj\n4 0 obj<</Length 8>>stream\nBT ET\nendstream endobj\nxref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n0000000104 00000 n \n0000000203 00000 n \ntrailer<</Size 5/Root 1 0 R>>\nstartxref\n281\n%%EOF")

@pytest.fixture()
def client(monkeypatch):
    """Provide a Flask test client with isolated temp DB.

    Key: set DATABASE_PATH before importing doc_processor modules so config_manager picks it up.
    """
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, 'test.db')
    pdf_path = os.path.join(tmp, 'sample.pdf')
    with open(pdf_path, 'wb') as f:
        f.write(sample_pdf_bytes())
    # Ensure env var visible before config_manager load
    monkeypatch.setenv('DATABASE_PATH', db_path)
    make_min_db(db_path, pdf_path)
    # Import after env set
    from doc_processor import app as app_module, database as db_module
    reload(app_module)
    reload(db_module)

    def _test_conn_factory():
        # Ensure database file exists
        if not os.path.exists(db_path):
            make_min_db(db_path, pdf_path)
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c

    # Patch DAL and API module reference
    monkeypatch.setattr(db_module, 'get_db_connection', _test_conn_factory, raising=True)
    from doc_processor.routes import api as api_module
    monkeypatch.setattr(api_module, 'get_db_connection', _test_conn_factory, raising=True)

    assert os.path.exists(db_path), "Temp database was not created"

    app = app_module.create_app()
    yield app.test_client()
    shutil.rmtree(tmp)

def j(resp):
    return json.loads(resp.data.decode('utf-8'))

@pytest.mark.parametrize('mode', ['llm_only','ocr','ocr_and_llm'])
def test_rescan_basic_modes(client, mode):
    r = client.post(f'/api/rescan_document/1', json={'rescan_type': mode})
    assert r.status_code == 200
    data = j(r)
    assert data['success']
    assert data['data']['document_id'] == 1
    assert data['data']['mode'] == mode
    # Flags present
    assert 'updated' in data['data']
    # ai fields should still be present (may or may not change in placeholder OCR)

def test_llm_failure_preserves_previous(monkeypatch, client):
    # Force AI function to raise to ensure previous values remain
    from doc_processor import llm_utils
    def boom(*a, **k): raise RuntimeError('LLM offline')
    monkeypatch.setattr(llm_utils, 'get_ai_document_type_analysis', boom)
    r = client.post('/api/rescan_document/1', json={'rescan_type': 'llm_only'})
    assert r.status_code == 200
    data = j(r)['data']
    assert data['ai_category'] == 'PrevCat'
    assert data['ai_filename'] == 'prev_file'
    assert data['ai_summary'] == 'Previous summary'
    assert data['ai_error'] is not None

def test_document_not_found(client):
    r = client.post('/api/rescan_document/999', json={'rescan_type': 'ocr_and_llm'})
    assert r.status_code == 404


def test_mode_effects_and_rotation(monkeypatch, client):
    """Ensure OCR-only does not change AI fields, LLM-only does not change OCR text length, and rotation_applied present.

    We insert a logical rotation and verify it's returned. We also capture baseline values then run different modes.
    """
    # Insert rotation into document_rotations
    from doc_processor.routes import api as api_module
    conn = api_module.get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO document_rotations (document_id, rotation) VALUES (1, 90)")
    conn.commit(); conn.close()

    # Baseline fetch (llm_only no change expected to OCR text)
    base = j(client.post('/api/rescan_document/1', json={'rescan_type': 'llm_only'}))['data']
    base_ocr_len = base['ocr_text_len']
    base_ai_cat = base['ai_category']
    assert 'rotation_applied' in base

    # OCR only (should update OCR maybe, but not AI). We allow OCR text length to change but AI fields persist.
    ocr_resp = j(client.post('/api/rescan_document/1', json={'rescan_type': 'ocr'}))['data']
    assert ocr_resp['mode'] == 'ocr'
    assert ocr_resp['ai_category'] == base_ai_cat
    assert 'ocr_dpi' in ocr_resp
    assert ocr_resp['rotation_applied'] in (0,90,180,270)

    # LLM only again - should not change OCR text len
    llm_resp = j(client.post('/api/rescan_document/1', json={'rescan_type': 'llm_only'}))['data']
    assert llm_resp['mode'] == 'llm_only'
    assert llm_resp['ocr_text_len'] == ocr_resp['ocr_text_len']
    assert llm_resp['rotation_applied'] in (0,90,180,270)

    # Full rescan
    full_resp = j(client.post('/api/rescan_document/1', json={'rescan_type': 'ocr_and_llm'}))['data']
    assert full_resp['mode'] == 'ocr_and_llm'
    assert full_resp['rotation_applied'] in (0,90,180,270)
    assert 'ocr_dpi' in full_resp


def test_llm_only_classification_populates_category(monkeypatch, client):
    """Patch get_ai_classification to return a known category and ensure endpoint stores it without OCR change."""
    from doc_processor import processing
    monkeypatch.setattr(processing, 'get_ai_classification', lambda text: 'Invoice')
    # Ensure filename suggestion deterministic
    monkeypatch.setattr(processing, 'get_ai_suggested_filename', lambda text, cat: '2025_Invoice_Test')
    resp = client.post('/api/rescan_document/1', json={'rescan_type': 'llm_only'})
    assert resp.status_code == 200
    data = j(resp)['data']
    assert data['mode'] == 'llm_only'
    assert data['ai_category'] == 'Invoice'
    assert data['ai_filename'] == '2025_Invoice_Test'


def test_filename_caching_and_confidence(monkeypatch, client):
    """Ensure filename not regenerated when OCR text hash unchanged and confidence/summary recorded."""
    from doc_processor import processing
    # First classification returns category + reasoning JSON
    def detailed_ok(text):
        return { 'category': 'Receipt', 'confidence': 82, 'reasoning': 'Looks like a receipt with totals.' }
    monkeypatch.setattr(processing, 'get_ai_classification_detailed', detailed_ok)
    monkeypatch.setattr(processing, 'get_ai_suggested_filename', lambda text, cat: '2025_Receipt_First')
    first = j(client.post('/api/rescan_document/1', json={'rescan_type': 'llm_only'}))['data']
    assert first['ai_category'] == 'Receipt'
    assert first['ai_filename'] == '2025_Receipt_First'
    assert first['ai_confidence'] is not None
    # Second run: swap filename generator to prove caching prevents change
    monkeypatch.setattr(processing, 'get_ai_suggested_filename', lambda text, cat: '2025_Receipt_Second')
    second = j(client.post('/api/rescan_document/1', json={'rescan_type': 'llm_only'}))['data']
    # Should retain original filename due to identical OCR hash
    assert second['ai_filename'] == '2025_Receipt_First'


import sqlite3
import pytest
from doc_processor.app import create_app
from doc_processor.config_manager import AppConfig
import doc_processor.config_manager as _cfg_mod

@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Directories
    intake = tmp_path / 'intake'; intake.mkdir()
    filing = tmp_path / 'filing_cabinet'; filing.mkdir()
    processed = tmp_path / 'processed'; processed.mkdir()
    db_path = tmp_path / 'export.db'
    monkeypatch.setenv('DATABASE_PATH', str(db_path))
    monkeypatch.setenv('INTAKE_DIR', str(intake))
    monkeypatch.setenv('FILING_CABINET_DIR', str(filing))
    monkeypatch.setenv('PROCESSED_DIR', str(processed))
    monkeypatch.setenv('WIP_DIR', str(processed))
    monkeypatch.setenv('ENABLE_TAG_EXTRACTION', '0')
    monkeypatch.setenv('FAST_TEST_MODE', '1')  # still speed mode

    # Reload config & rebind
    _cfg_mod.app_config = AppConfig.load_from_env()
    import doc_processor.processing as _proc_mod
    import doc_processor.routes.export as _export_mod
    _proc_mod.app_config = _cfg_mod.app_config
    _export_mod.app_config = _cfg_mod.app_config

    # DB schema
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE batches (id INTEGER PRIMARY KEY AUTOINCREMENT, status TEXT, has_been_manipulated INTEGER DEFAULT 0);
        CREATE TABLE single_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            original_filename TEXT NOT NULL,
            original_pdf_path TEXT,
            searchable_pdf_path TEXT,
            page_count INTEGER DEFAULT 1,
            ocr_text TEXT,
            ocr_confidence_avg REAL,
            ai_suggested_category TEXT,
            ai_suggested_filename TEXT,
            ai_confidence REAL,
            ai_summary TEXT,
            final_category TEXT,
            final_filename TEXT,
            status TEXT DEFAULT 'processing'
        );
        CREATE TABLE categories (name TEXT PRIMARY KEY, is_active INTEGER DEFAULT 1);
        INSERT INTO categories(name,is_active) VALUES ('Reports',1);
        INSERT INTO batches(id,status) VALUES (1,'processing');
        """
    )

    # Seed two docs: one with pre-existing searchable pdf, one without
    pre_pdf = intake / 'pre.pdf'
    with open(pre_pdf,'wb') as f: f.write(b'%PDF-1.4 PRE')
    cached_searchable = intake / 'pre_cached_searchable.pdf'
    with open(cached_searchable,'wb') as f: f.write(b'%PDF-1.4 CACHED')

    with open(intake / 'new.pdf','wb') as f: f.write(b'%PDF-1.4 NEW')

    cur.execute("""INSERT INTO single_documents(batch_id, original_filename, original_pdf_path, searchable_pdf_path, final_category, final_filename)
                  VALUES (1,?,?,?,?,?)""",
                ('pre.pdf', str(pre_pdf), str(cached_searchable), 'Reports', 'pre_final'))
    cur.execute("""INSERT INTO single_documents(batch_id, original_filename, original_pdf_path, final_category, final_filename)
                  VALUES (1,?,?,?,?)""",
                ('new.pdf', str(intake/'new.pdf'), 'Reports', 'new_final'))
    conn.commit(); conn.close()

    app = create_app(); app.config['TESTING']=True
    with app.test_client() as c:
        yield c, tmp_path


def test_export_respects_cached_searchable(client):
    c, base = client
    resp = c.post('/export/finalize_single_documents_batch/1', data={'force':'1'})
    assert resp.status_code == 200 and resp.get_json().get('success')

    # Wait for completion
    for _ in range(40):
        prog = c.get('/export/api/progress').get_json()
        if prog.get('data'):
            status = prog['data'].get('1') or prog['data'].get(1)
            if status and status.get('status') in ('completed','error'):
                break
        import time; time.sleep(0.05)
    else:
        pytest.fail('Export timeout')

    # use filing cabinet path from base fixture
    reports = base / 'filing_cabinet' / 'Reports'
    assert reports.exists()
    artifacts = {p.name: p for p in reports.iterdir()}

    # Cached searchable should have been copied (content starts with CACHED)
    cached = artifacts.get('pre_final_searchable.pdf')
    assert cached and cached.read_bytes().startswith(b'%PDF-1.4 CACHED')

    # New doc should have fallback (copy of original NEW)
    new_cached = artifacts.get('new_final_searchable.pdf')
    assert new_cached and new_cached.read_bytes().startswith(b'%PDF-1.4 NEW')

    # Ensure original cached file not overwritten
    assert (base/'intake'/'pre_cached_searchable.pdf').read_bytes().startswith(b'%PDF-1.4 CACHED')

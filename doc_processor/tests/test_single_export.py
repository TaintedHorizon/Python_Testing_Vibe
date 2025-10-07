import os, sqlite3, tempfile, shutil, json, re
import pytest

# IMPORTANT: set global fast/test flags BEFORE importing app factory so config_manager picks them up
os.environ.setdefault('ENABLE_TAG_EXTRACTION', '0')  # disable LLM tagging for speed
os.environ.setdefault('FAST_TEST_MODE', '1')

from doc_processor.app import create_app
from doc_processor import config_manager as _cfg_mod
from doc_processor.config_manager import AppConfig, app_config

@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Setup isolated dirs
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
    monkeypatch.setenv('FAST_TEST_MODE', '1')

    # Reload configuration with updated paths
    _cfg_mod.app_config = AppConfig.load_from_env()
    # Rebind in already-imported modules capturing old instance
    import doc_processor.processing as _proc_mod
    import doc_processor.routes.export as _export_mod
    _proc_mod.app_config = _cfg_mod.app_config
    _export_mod.app_config = _cfg_mod.app_config

    # Build minimal schema and seed data
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript("""
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
    """)
    # Create three sample docs mixing pdf and image to exercise raw image export path
    # Real files are not strictly required because finalize just copies if exists; create dummy files.
    for idx,(fname,ext,cat) in enumerate([
        ('alpha','pdf','Reports'),
        ('scan1','jpg','Reports'),
        ('notes','pdf','Reports')
    ], start=1):
        src_path = intake / f"{fname}.{ext}"
        with open(src_path,'wb') as f: f.write(b'%PDF-1.4' if ext=='pdf' else b'\xff\xd8jpgmock')
        cur.execute("""INSERT INTO single_documents(batch_id, original_filename, original_pdf_path, page_count, ai_suggested_category, ai_suggested_filename, final_category, final_filename)
                       VALUES (1,?,?,?,?,?,?,?)""",
                    (f"{fname}.{ext}", str(src_path), 1, cat, f"{fname}_ai", cat, f"{fname}_final"))
    conn.commit(); conn.close()

    # Create app after env vars to ensure config picks them up
    app = create_app(); app.config['TESTING']=True
    with app.test_client() as c:
        yield c, tmp_path


def test_single_document_finalize_export(client):
    c, base = client
    # Trigger export
    resp = c.post('/export/finalize_single_documents_batch/1', data={'force':'1'})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload and payload.get('success')

    # Poll progress endpoint until completion
    for _ in range(40):
        prog = c.get('/export/api/progress').get_json()
        assert prog.get('success')
        status_map = prog['data']
        if status_map:
            batch_status = status_map.get('1') or status_map.get(1)
            if batch_status and batch_status.get('status') in ('completed','error'):
                break
        import time; time.sleep(0.05)
    else:
        pytest.fail('Export did not complete in time')

    # Inspect filing cabinet outputs
    filing_dir = base / 'filing_cabinet'
    exported = list(filing_dir.rglob('*'))
    # Expect category folder 'Reports'
    reports_dir = filing_dir / 'Reports'
    assert reports_dir.exists()

    # Collect produced artifacts for the JPG (should have _source.jpg) and for PDFs (_original.pdf)
    artifacts = sorted(p.name for p in reports_dir.iterdir())
    # Minimal expectations
    assert any(a.endswith('_searchable.pdf') for a in artifacts)
    assert any(a.endswith('.md') for a in artifacts)
    # Raw image preserved
    assert any(a.endswith('_source.jpg') for a in artifacts)
    # Original pdf alias preserved
    assert any(a.endswith('_original.pdf') for a in artifacts)

    # Basic markdown content sanity: pick one file and check key headings
    md_files = [p for p in reports_dir.glob('*.md')]
    assert md_files, 'No markdown files exported'
    sample_md = md_files[0].read_text(encoding='utf-8')
    assert '# ' in sample_md
    assert 'AI Suggested Category' in sample_md
    assert 'OCR Text' in sample_md

    # Ensure no placeholder python exception text in markdown
    assert 'Traceback' not in sample_md

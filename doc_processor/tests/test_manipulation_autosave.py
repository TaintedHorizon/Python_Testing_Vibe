import sqlite3
import pytest
from doc_processor.app import create_app

@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / 'auto.db'
    monkeypatch.setenv('DATABASE_PATH', str(db_path))
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE batches (id INTEGER PRIMARY KEY AUTOINCREMENT, status TEXT, has_been_manipulated INTEGER DEFAULT 0);
    CREATE TABLE single_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        original_filename TEXT NOT NULL,
        original_pdf_path TEXT,
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

    from .test_utils import write_valid_pdf

    alpha = tmp_path / 'alpha.pdf'
    write_valid_pdf(alpha)
    cur.execute(
        "INSERT INTO single_documents(batch_id, original_filename, original_pdf_path, page_count, ocr_text, ocr_confidence_avg, ai_suggested_category, ai_suggested_filename, ai_confidence) VALUES (?,?,?,?,?,?,?,?,?)",
        (1, 'alpha.pdf', str(alpha), 1, 'OCR BODY', 81.2, 'Reports', 'alpha_ai', 0.91)
    )
    conn.commit(); conn.close()
    app = create_app(); app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

def _fetch_doc(db_path):
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT final_category, final_filename FROM single_documents WHERE id=1").fetchone()
    conn.close()
    return row

def test_autosave_updates_document(client, tmp_path):
    db_path = tmp_path / 'auto.db'
    # POST auto_save
    resp = client.post('/document/batch/1/manipulate/1', data={
        'doc_id': '1',
        'action': 'auto_save',
        'category_dropdown': 'Reports',
        'filename_choice': 'ai'
    })
    assert resp.status_code == 200
    assert b'success' in resp.data  # JSON response
    cat, fname = _fetch_doc(db_path)
    # final_category/final_filename may be None if AI suggestion used and we didn't explicitly set; ensure no error path
    # For this auto-save we expect final_category to have been persisted to 'Reports'
    assert cat == 'Reports'

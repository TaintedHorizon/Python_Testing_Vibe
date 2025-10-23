import sqlite3
import pytest
from doc_processor.app import create_app

@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / 'norm.db'
    monkeypatch.setenv('DATABASE_PATH', str(db_path))
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS batches (id INTEGER PRIMARY KEY AUTOINCREMENT, status TEXT, has_been_manipulated INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS single_documents (
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
    CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY, is_active INTEGER DEFAULT 1);
    """)
    # Insert rows using tmp_path-based sample PDFs
    cur.execute("INSERT INTO categories(name,is_active) VALUES (?,?)", ('Reports', 1))
    cur.execute("INSERT INTO batches(id,status) VALUES (?,?)", (1, 'processing'))
    alpha = tmp_path / 'alpha.pdf'
    beta = tmp_path / 'beta.pdf'
    gamma = tmp_path / 'gamma.pdf'
    alpha.write_bytes(b'%PDF-1.4 ALPHA')
    beta.write_bytes(b'%PDF-1.4 BETA')
    gamma.write_bytes(b'%PDF-1.4 GAMMA')
    cur.execute("INSERT INTO single_documents(batch_id, original_filename, original_pdf_path, page_count, ai_suggested_category, ai_suggested_filename) VALUES (?,?,?,?,?,?)",
                (1, 'alpha.pdf', str(alpha), 1, 'Reports', 'alpha_ai'))
    cur.execute("INSERT INTO single_documents(batch_id, original_filename, original_pdf_path, page_count, ai_suggested_category, ai_suggested_filename) VALUES (?,?,?,?,?,?)",
                (1, 'beta.pdf', str(beta), 1, 'Reports', 'beta_ai'))
    cur.execute("INSERT INTO single_documents(batch_id, original_filename, original_pdf_path, page_count, ai_suggested_category, ai_suggested_filename) VALUES (?,?,?,?,?,?)",
                (1, 'gamma.pdf', str(gamma), 1, 'Reports', 'gamma_ai'))
    conn.commit(); conn.close()
    app = create_app(); app.config['TESTING']=True
    with app.test_client() as c:
        yield c, db_path

def _fetch_finals(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, final_category, final_filename FROM single_documents ORDER BY id").fetchall()
    conn.close()
    return rows

def test_finalize_normalization_populates_missing_fields(client):
    c, db_path = client
    # finalize on last doc (doc_num 3)
    resp = c.post('/document/batch/1/manipulate/3', data={
        'doc_id': '3',
        'action': 'finish_batch',
        'category_dropdown': '',  # simulate no explicit selection
        'filename_choice': 'ai'
    }, follow_redirects=False)
    assert resp.status_code in (302, 303)  # redirect to batch control
    finals = _fetch_finals(db_path)
    # All docs should now have final_category and final_filename
    for _id, cat, fname in finals:
        assert cat is not None
        assert fname is not None
        assert fname != ''


def test_new_category_insertion_and_assignment(client):
    c, db_path = client
    # Add a new category through doc 1
    resp = c.post('/document/batch/1/manipulate/1', data={
        'doc_id': '1',
        'action': 'auto_save',
        'category_dropdown': 'other_new',
        'other_category': 'Invoices',
        'filename_choice': 'ai'
    })
    assert resp.status_code == 200
    # Ensure category inserted and assigned
    conn = sqlite3.connect(db_path)
    cat_row = conn.execute("SELECT name FROM categories WHERE name='Invoices'").fetchone()
    doc_row = conn.execute("SELECT final_category FROM single_documents WHERE id=1").fetchone()
    conn.close()
    assert cat_row is not None
    assert doc_row is not None and doc_row[0] == 'Invoices'

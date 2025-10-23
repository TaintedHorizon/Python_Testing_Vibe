import sqlite3
import pytest
from doc_processor.app import create_app

@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Create a temporary database file
    db_path = tmp_path / 'test.db'
    # Point config to temp DB
    monkeypatch.setenv('DATABASE_PATH', str(db_path))

    # Initialize minimal schema for batches + single_documents
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Create schema using executescript and then insert rows with parameterized values
    cur.executescript("""
    CREATE TABLE batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT,
        has_been_manipulated INTEGER DEFAULT 0
    );
    CREATE TABLE single_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        original_filename TEXT NOT NULL,
        original_pdf_path TEXT,
        ai_suggested_category TEXT,
        ai_suggested_filename TEXT,
        ai_confidence REAL,
        ai_summary TEXT,
        ocr_text TEXT,
        ocr_confidence_avg REAL,
        final_category TEXT,
        final_filename TEXT,
        status TEXT DEFAULT 'processing'
    );
    CREATE TABLE categories (name TEXT PRIMARY KEY, is_active INTEGER DEFAULT 1);
    """)

    # Insert initial data with temp paths
    cur.execute("INSERT INTO categories(name,is_active) VALUES (?,?)", ('Invoices', 1))
    cur.execute("INSERT INTO batches(id,status) VALUES (?,?)", (1, 'processing'))
    sample_pdf = tmp_path / 'sample.pdf'
    sample_pdf.write_bytes(b"%PDF-1.4 sample")
    cur.execute(
        "INSERT INTO single_documents(batch_id, original_filename, original_pdf_path, ai_suggested_category, ai_suggested_filename, ai_confidence, ai_summary, ocr_text, ocr_confidence_avg) VALUES (?,?,?,?,?,?,?,?,?)",
        (1, 'sample.pdf', str(sample_pdf), 'Invoices', 'invoice_sample', 0.87, 'Summary', 'OCR TEXT', 78.5)
    )
    conn.commit()
    conn.close()

    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_manipulate_get_single_document(client):
    resp = client.get('/document/batch/1/manipulate')
    assert resp.status_code == 200
    # Should show Document 1 of 1
    assert b'Document 1 of 1' in resp.data
    assert b'Invoices' in resp.data
    assert b'invoice_sample' in resp.data


def test_manipulate_post_finish_batch(client):
    # Post finish batch to set final values
    resp = client.post('/document/batch/1/manipulate/1', data={
        'doc_id': '1',
        'action': 'finish_batch',
        'category_dropdown': 'Invoices',
        'filename_choice': 'ai'
    }, follow_redirects=True)
    assert resp.status_code == 200
    # Redirected back to batch control (placeholder) or success flash present
    # We at least ensure no error occurred
    assert b'Batch Control' in resp.data or b'All changes saved' in resp.data

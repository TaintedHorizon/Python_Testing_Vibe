import os, tempfile, sqlite3, time, sys
from pathlib import Path
from flask import Flask

# Establish a placeholder DATABASE_PATH early so config_manager uses an isolated temp DB
_TEST_DB_PLACEHOLDER = os.path.join(tempfile.gettempdir(), 'rotation_test_placeholder.db')
os.environ.setdefault('DATABASE_PATH', _TEST_DB_PLACEHOLDER)

# Ensure project root on path when running test directly/isolated
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from doc_processor.app import create_app  # type: ignore
from doc_processor.config_manager import app_config

# NOTE: This test focuses on rotation serving logic. It seeds a single_documents row
# plus intake_rotations entry, then requests the PDF through the manipulation route.

def _ensure_tables(conn):
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS single_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER,
        original_filename TEXT,
        original_pdf_path TEXT,
        page_count INTEGER,
        file_size_bytes INTEGER,
        status TEXT,
        ai_suggested_category TEXT,
        ai_suggested_filename TEXT,
        ai_confidence REAL,
        ai_summary TEXT,
        ocr_text TEXT,
        ocr_confidence_avg REAL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS intake_rotations (
        filename TEXT PRIMARY KEY,
        rotation INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()


def test_rotation_serving():
    """Integration test for /document/serve_single_pdf/<id> rotation caching.

    Flow:
      1. Create isolated temp DB (already configured via _TEST_DB_PLACEHOLDER at import)
      2. Generate a simple one-page PDF inside allowed INTAKE_DIR
      3. Seed single_documents + intake_rotations (90°)
      4. Request served PDF (rotated cache generated)
      5. Update rotation to 180° (timestamp bumps)
      6. Request again and assert bytes differ (cache invalidation + regeneration)
    """
    import fitz

    # Ensure INTAKE_DIR exists and create PDF there (path validation requires allowed dirs)
    intake_dir = Path(app_config.INTAKE_DIR)
    intake_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = intake_dir / "orig.pdf"
    if pdf_path.exists():
        pdf_path.unlink()
    doc = fitz.open()
    # Use insert_page which exists across PyMuPDF versions; then write text
    # PyMuPDF page creation (handle both modern and legacy names). Lint may not know dynamic attributes.
    try:  # noqa: SIM105
        page = doc.new_page()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        page = doc.newPage()  # type: ignore[attr-defined]
    page.insert_text((72,72), "RotationTest")  # type: ignore[attr-defined]
    doc.save(str(pdf_path))
    doc.close()

    # App already imported with placeholder DATABASE_PATH
    db_path = Path(app_config.DATABASE_PATH)
    # Start clean
    if db_path.exists():
        os.remove(db_path)

    # Seed database (prefer the centralized helper so PRAGMA and WAL are applied)
    try:
        from doc_processor.database import get_db_connection
        conn = get_db_connection()
    except Exception:
        conn = sqlite3.connect(db_path)
    _ensure_tables(conn)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO single_documents (batch_id, original_filename, original_pdf_path, page_count, file_size_bytes, status) VALUES (?,?,?,?,?,?)",
        (999, 'orig.pdf', str(pdf_path), 1, os.path.getsize(pdf_path), app_config.STATUS_READY_FOR_MANIPULATION)
    )
    doc_id = cur.lastrowid
    cur.execute("INSERT INTO intake_rotations (filename, rotation) VALUES (?, ?)", ('orig.pdf', 90))
    conn.commit()
    conn.close()

    # Build app AFTER seeding so route can read from DB immediately
    app = create_app()
    client = app.test_client()

    # First request (should be 90° rotated cache)
    resp1 = client.get(f"/document/serve_single_pdf/{doc_id}")
    assert resp1.status_code == 200, f"Initial serve failed: {resp1.status_code} {resp1.data[:200]}"
    data1 = resp1.data
    assert len(data1) > 100

    # Update rotation to 180° (regeneration expected)
    try:
        from doc_processor.database import get_db_connection
        conn = get_db_connection()
    except Exception:
        conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE intake_rotations SET rotation = ?, updated_at = CURRENT_TIMESTAMP WHERE filename = ?", (180, 'orig.pdf'))
    conn.commit()
    conn.close()

    time.sleep(1)  # ensure mtime difference for cache invalidation
    resp2 = client.get(f"/document/serve_single_pdf/{doc_id}")
    assert resp2.status_code == 200, f"Second serve failed: {resp2.status_code} {resp2.data[:200]}"
    data2 = resp2.data
    assert data1 != data2, "Rotated PDF should regenerate after rotation change (byte content identical)"

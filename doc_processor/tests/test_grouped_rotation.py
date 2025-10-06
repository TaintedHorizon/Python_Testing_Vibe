import os
import sqlite3
import time
from pathlib import Path
import fitz  # PyMuPDF

from doc_processor.config_manager import app_config

def _create_pdf(path: Path, text: str, rotate: int = 0):
    doc = fitz.open()
    try:
        page = doc.new_page()  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover
        page = doc.newPage()  # type: ignore[attr-defined]
    page.insert_text((72,72), text)
    if rotate:
        page.set_rotation(rotate)
    doc.save(str(path))
    doc.close()


def test_grouped_document_rotation_serving(client, seed_conn, temp_db_path):
    """Ensure grouped-document path shows rotation parity via single-doc route logic.

    We simulate a grouped document by creating a single_documents row because the
    current serving route (`/document/serve_single_pdf/<id>`) operates only on the
    single-document workflow. This test asserts parity expectations remain intact
    until a dedicated grouped-document route is implemented.
    """
    # Minimal schema for single_documents
    cur = seed_conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS single_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER,
        original_filename TEXT,
        original_pdf_path TEXT,
        page_count INTEGER,
        file_size_bytes INTEGER,
        status TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS intake_rotations (filename TEXT PRIMARY KEY, rotation INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    seed_conn.commit()

    # Create PDF in INTAKE_DIR
    intake_dir = Path(app_config.INTAKE_DIR)
    intake_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = intake_dir / "grouped_orig.pdf"
    _create_pdf(pdf_path, "GroupedRotationTest")

    # Insert row and rotation 270°
    cur.execute("INSERT INTO single_documents (batch_id, original_filename, original_pdf_path, page_count, file_size_bytes, status) VALUES (?,?,?,?,?,?)",
                (123, 'grouped_orig.pdf', str(pdf_path), 1, os.path.getsize(pdf_path), app_config.STATUS_READY_FOR_MANIPULATION))
    doc_id = cur.lastrowid
    cur.execute("INSERT INTO intake_rotations (filename, rotation) VALUES (?, ?)", ("grouped_orig.pdf", 270))
    seed_conn.commit()

    r1 = client.get(f"/document/serve_single_pdf/{doc_id}")
    assert r1.status_code == 200
    b1 = r1.data

    # Change rotation to 180°, ensure regeneration
    cur.execute("UPDATE intake_rotations SET rotation=?, updated_at=CURRENT_TIMESTAMP WHERE filename=?", (180, 'grouped_orig.pdf'))
    seed_conn.commit()
    time.sleep(1)
    r2 = client.get(f"/document/serve_single_pdf/{doc_id}")
    assert r2.status_code == 200
    b2 = r2.data
    assert b1 != b2, "Expected regenerated rotated PDF for grouped-doc parity"


def test_no_double_rotation(client, seed_conn, temp_db_path):
    """If PDF is already physically rotated and DB rotation matches, do not re-rotate.

    Steps:
      1. Create a PDF and physically rotate its page 90°.
      2. Insert single_documents row and set rotation table to 90°.
      3. First fetch returns bytes (rotated). Second fetch after touching timestamp but keeping same angle should yield identical bytes (cache reuse, no re-rotate).
    """
    cur = seed_conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS single_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER,
        original_filename TEXT,
        original_pdf_path TEXT,
        page_count INTEGER,
        file_size_bytes INTEGER,
        status TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS intake_rotations (filename TEXT PRIMARY KEY, rotation INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    seed_conn.commit()

    intake_dir = Path(app_config.INTAKE_DIR)
    intake_dir.mkdir(parents=True, exist_ok=True)
    phys_path = intake_dir / "phys_rotated.pdf"
    _create_pdf(phys_path, "PhysRotated", rotate=90)

    cur.execute("INSERT INTO single_documents (batch_id, original_filename, original_pdf_path, page_count, file_size_bytes, status) VALUES (?,?,?,?,?,?)",
                (321, 'phys_rotated.pdf', str(phys_path), 1, os.path.getsize(phys_path), app_config.STATUS_READY_FOR_MANIPULATION))
    doc_id = cur.lastrowid
    cur.execute("INSERT INTO intake_rotations (filename, rotation) VALUES (?, ?)", ('phys_rotated.pdf', 90))
    seed_conn.commit()

    r1 = client.get(f"/document/serve_single_pdf/{doc_id}")
    assert r1.status_code == 200
    d1 = r1.data

    # Touch timestamp without changing angle
    cur.execute("UPDATE intake_rotations SET updated_at=CURRENT_TIMESTAMP WHERE filename=?", ('phys_rotated.pdf',))
    seed_conn.commit()
    time.sleep(1)
    r2 = client.get(f"/document/serve_single_pdf/{doc_id}")
    assert r2.status_code == 200
    d2 = r2.data
    assert d1 == d2, "Expected identical bytes (no double-rotation) when physical and stored rotation align"

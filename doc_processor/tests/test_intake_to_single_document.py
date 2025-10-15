import os
import shutil
import time

import pytest

# Import app factory and DB helper inside the test after env setup so config picks up env overrides


@pytest.mark.timeout(60)
def test_intake_creates_single_document(client, temp_intake_dir, mocked_ollama):
    # Copy fixture into the temp intake dir provided by the fixture
    repo_sample = os.path.join(os.path.dirname(__file__), "fixtures", "sample_small.pdf")
    assert os.path.exists(repo_sample), f"Sample PDF missing: {repo_sample}"
    dest_pdf = os.path.join(temp_intake_dir, "sample_intake.pdf")
    shutil.copy2(repo_sample, dest_pdf)

    # Start a new processing batch via the test client
    with client.application.app_context():
        resp = client.post("/batch/start_new", data={})
        assert resp.status_code in (200, 302)

        # Query the temp DB to find batch id
        from doc_processor.database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM batches ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        assert row is not None, "No batch created"
        batch_id = row[0]

        # Trigger smart processing with immediate background run
        resp = client.post("/batch/process_smart", data={"batch_id": batch_id, "start_immediately": "1"})
        assert resp.status_code == 200

    # Allow background processing to complete
    time.sleep(1)

    # Check the DB for the created single_document row
    cur.execute("PRAGMA table_info(single_documents)")
    cols = [r[1] for r in cur.fetchall()]
    if "original_filename" in cols:
        fname_col = "original_filename"
    elif "source_filename" in cols:
        fname_col = "source_filename"
    else:
        fname_col = "ai_suggested_filename"

    cur.execute(
        f"SELECT id, batch_id, {fname_col} FROM single_documents WHERE {fname_col} = ? ORDER BY id DESC LIMIT 1",
        ("sample_intake.pdf",),
    )
    doc_row = cur.fetchone()
    assert doc_row is not None, f"single_documents row was not created (checked column {fname_col})"

import os
import sqlite3
from doc_processor.batch_guard import get_or_create_intake_batch, cleanup_empty_processing_batches, create_new_batch
from doc_processor.database import get_db_connection


def test_create_and_reuse_intake_batch(tmp_path, monkeypatch):
    # Use a temporary DB by copying existing DB to tmp_path and pointing get_db_connection to it
    src = os.path.join(os.path.dirname(__file__), '..', 'documents.db')
    dst = tmp_path / 'documents.db'
    import shutil
    shutil.copy2(src, dst)

    # Monkeypatch get_db_connection to use tmp DB
    def _get_db_connection():
        conn = sqlite3.connect(str(dst))
        conn.row_factory = sqlite3.Row
        return conn
    monkeypatch.setattr('doc_processor.database.get_db_connection', _get_db_connection)

    # Ensure no processing batches exist by cleaning up
    cleaned = cleanup_empty_processing_batches()

    # Create an intake batch via helper
    b1 = get_or_create_intake_batch()
    assert isinstance(b1, int)

    # Attempt to get or create again - should reuse
    b2 = get_or_create_intake_batch()
    assert b1 == b2

    # Create a new processing batch via create_new_batch and ensure it returns int
    b3 = create_new_batch('processing')
    assert isinstance(b3, int)

    # Cleanup should not remove batches with documents; ensure function returns a list
    res = cleanup_empty_processing_batches()
    assert isinstance(res, list)

from doc_processor.batch_guard import get_or_create_intake_batch, cleanup_empty_processing_batches, create_new_batch


def test_create_and_reuse_intake_batch(tmp_path, monkeypatch):
    # Create an isolated temporary DB in tmp_path and point get_db_connection to it
    dst = tmp_path / 'documents.db'
    dst_parent = dst.parent
    dst_parent.mkdir(parents=True, exist_ok=True)
    # Set env to point the app at our tmp DB and allow creation
    monkeypatch.setenv('DATABASE_PATH', str(dst))
    monkeypatch.setenv('ALLOW_NEW_DB', '1')

    # Create minimal schema using the same database_connection helper the application uses
    from doc_processor.processing import database_connection
    with database_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT,
                created_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS single_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER,
                original_pdf_path TEXT
            )
        """)
        conn.commit()
    # Ensure batch_guard uses the same database_connection (avoid fallback to local-file DB)
    import doc_processor.processing as proc_mod
    # Ensure batch_guard uses the same database_connection helper by patching the module object
    import doc_processor.batch_guard as batch_guard_mod
    monkeypatch.setattr(batch_guard_mod, 'database_connection', proc_mod.database_connection)
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

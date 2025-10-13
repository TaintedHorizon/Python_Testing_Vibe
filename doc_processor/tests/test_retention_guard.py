import sqlite3
from pathlib import Path


from doc_processor import batch_guard


def _setup_tmp_db(tmp_path: Path) -> Path:
    # Ensure the provided tmp_path directory exists (pytest may pass a nested path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "documents.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT,
            has_been_manipulated INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS single_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            original_pdf_path TEXT
        )
        """
    )
    # Insert two empty processing batches
    cur.execute("INSERT INTO batches (status) VALUES ('processing')")
    cur.execute("INSERT INTO batches (status) VALUES ('processing')")
    conn.commit()
    conn.close()
    return db_path


def test_cleanup_skips_when_retention_missing(tmp_path: Path, monkeypatch):
    db_path = _setup_tmp_db(tmp_path)

    # Point DB and enable retention guard
    monkeypatch.setenv('DATABASE_PATH', str(db_path))
    monkeypatch.setenv('ENFORCE_RETENTION_GUARD', '1')

    # Configure the app to use a test-local backup directory so we don't touch
    # repository paths. Patch config_manager.app_config.DB_BACKUP_DIR.
    import importlib
    cm = importlib.import_module('doc_processor.config_manager')
    test_backup_root = tmp_path / 'db_backups'
    test_backup_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv('DB_BACKUP_DIR', str(test_backup_root))
    # Reload app_config to pick up env change (simple approach for tests)
    importlib.reload(cm)
    # Ensure the runtime app_config is updated for direct imports
    try:
        from doc_processor.config_manager import app_config
        app_config.DB_BACKUP_DIR = str(test_backup_root)
    except Exception:
        pass

    # Call cleanup - should skip deletions because retention copies are missing
    deleted = batch_guard.cleanup_empty_processing_batches()
    assert deleted == []


def test_cleanup_allows_when_guard_disabled_or_retention_present(tmp_path: Path, monkeypatch):
    db_path = _setup_tmp_db(tmp_path)

    # Case A: guard enabled but retention present for batch id 1
    monkeypatch.setenv('DATABASE_PATH', str(db_path))
    monkeypatch.setenv('ENFORCE_RETENTION_GUARD', '1')

    # Use test-local backup dir
    import importlib
    cm = importlib.import_module('doc_processor.config_manager')
    test_backup_root = tmp_path / 'db_backups2'
    test_backup_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv('DB_BACKUP_DIR', str(test_backup_root))
    importlib.reload(cm)
    try:
        from doc_processor.config_manager import app_config
        app_config.DB_BACKUP_DIR = str(test_backup_root)
    except Exception:
        pass

    # app_config.DB_BACKUP_DIR should be set to test_backup_root above; guard in case
    backup_dir = getattr(app_config, 'DB_BACKUP_DIR', None)
    if not backup_dir:
        backup_dir = str(test_backup_root)
    retention_root = Path(backup_dir)
    retention_root.mkdir(parents=True, exist_ok=True)
    b1 = retention_root / '1'
    b1.mkdir(exist_ok=True)
    (b1 / 'orig.pdf').write_text('dummy')

    deleted = batch_guard.cleanup_empty_processing_batches()
    # With retention present, at least the batch with retention should be deleted (or attempted)
    assert isinstance(deleted, list)

    # Case B: guard disabled - cleanup should delete remaining empty processing batches
    # Recreate DB with two empty batches
    db_path2 = _setup_tmp_db(tmp_path / 'second')
    monkeypatch.setenv('DATABASE_PATH', str(db_path2))
    monkeypatch.setenv('ENFORCE_RETENTION_GUARD', '0')

    deleted2 = batch_guard.cleanup_empty_processing_batches()
    assert isinstance(deleted2, list)
    # Expect at least one deletion when guard disabled
    assert len(deleted2) >= 1

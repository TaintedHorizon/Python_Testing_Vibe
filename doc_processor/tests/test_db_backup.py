import os
import importlib
from pathlib import Path

import pytest


def test_allow_new_db_backup_creates_timestamped_backup(tmp_path, monkeypatch):
    # Prepare a zero-byte existing DB file to trigger the backup path in get_db_connection
    db_file = tmp_path / "documents.db"
    db_file.write_bytes(b"")  # create empty file (size == 0)

    backup_dir = tmp_path / "backups"
    # Set environment variables BEFORE importing modules
    monkeypatch.setenv("DATABASE_PATH", str(db_file))
    monkeypatch.setenv("ALLOW_NEW_DB", "backup")
    monkeypatch.setenv("DB_BACKUP_DIR", str(backup_dir))

    # Reload config_manager and database modules to pick up env changes
    import doc_processor.config_manager as cfg
    importlib.reload(cfg)
    import doc_processor.database as database
    importlib.reload(database)

    # Call get_db_connection which should attempt the backup when ALLOW_NEW_DB=backup
    conn = database.get_db_connection()
    try:
        # After get_db_connection runs, a backup file should exist in DB_BACKUP_DIR
        backups = list(backup_dir.glob("documents.db.backup.*"))
        assert len(backups) >= 1, f"Expected a backup file under {backup_dir}, found: {backups}"
        # Backup file should be non-empty (copied file metadata present even if source empty)
        assert backups[0].exists()
    finally:
        if conn:
            conn.close()

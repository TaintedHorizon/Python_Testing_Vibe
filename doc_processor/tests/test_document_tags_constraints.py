import os
import sqlite3
from pathlib import Path

import pytest


def _get_temp_db_path(tmp_path: Path) -> str:
    # Match test fixtures: tests set DATABASE_PATH via env in conftest; emulate minimal DB creation
    db_file = tmp_path / "test.db"
    return str(db_file)


def test_document_tags_has_created_at_and_unique_index(tmp_path, monkeypatch):
    """Ensure the runtime creates document_tags.created_at column and a unique index on (document_id, tag_category, tag_value)."""
    db_path = _get_temp_db_path(tmp_path)
    monkeypatch.setenv('DATABASE_PATH', db_path)
    # Allow tests to create DB
    monkeypatch.setenv('ALLOW_NEW_DB', '1')
    # Import the app database module after envs set so get_db_connection uses them
    from doc_processor import database

    # Trigger connection which should initialize schema
    conn = database.get_db_connection()
    try:
        cur = conn.cursor()
        # Inspect columns
        cols = {row[1] for row in cur.execute("PRAGMA table_info(document_tags)").fetchall()}
        assert 'created_at' in cols, "document_tags.created_at column missing"

        # Look for unique index or constraint by checking index list + index_info
        indexes = [r[1] for r in cur.execute("PRAGMA index_list('document_tags')").fetchall()]
        has_unique_index = False
        for idx in indexes:
            info = cur.execute("PRAGMA index_info('%s')" % idx).fetchall()
            cols_in_idx = [r[2] for r in info]
            if cols_in_idx == ['document_id', 'tag_category', 'tag_value']:
                # Now check if index is unique
                meta = cur.execute("PRAGMA index_list('document_tags')").fetchall()
                for m in meta:
                    if m[1] == idx and m[2] == 1:
                        has_unique_index = True
                        break
            if has_unique_index:
                break

        # Some SQLite builds may represent UNIQUE as table constraint without a named index.
        # As a fallback, query sqlite_master for a UNIQUE clause.
        if not has_unique_index:
            master = ''.join(r[0] for r in cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='document_tags'").fetchall() if r[0])
            if 'UNIQUE(document_id, tag_category, tag_value)' in master.replace(' ', ''):
                has_unique_index = True

        assert has_unique_index, "Unique constraint/index on (document_id, tag_category, tag_value) missing"

    finally:
        conn.close()

"""Idempotent schema upgrade script to bring the database to full feature readiness.

Run after activating venv and ensuring DATABASE_PATH is set (via .env / config_manager).

Usage:
    python doc_processor/dev_tools/upgrade_full_schema.py [--dry-run]

What it does:
  * Creates missing tables: pages, categories, interaction_log, document_tags, tag_usage_stats
  * Adds missing columns to existing tables (batches, single_documents, pages, documents)
  * Reports actions taken or needed (dry run only prints) with a final readiness summary.

Safety:
  * Uses CREATE TABLE IF NOT EXISTS and column existence checks via PRAGMA table_info
  * Never drops or renames columns.
"""
from __future__ import annotations
import os, sqlite3, argparse, textwrap, sys, time
from pathlib import Path

REQUIRED_TABLES_SQL = {
    'pages': '''CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER,
        source_filename TEXT,
        page_number INTEGER,
        status TEXT DEFAULT 'pending_verification',
        human_verified_category TEXT,
        rotation_angle INTEGER DEFAULT 0,
        processed_image_path TEXT,
        ocr_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(batch_id) REFERENCES batches(id) ON DELETE CASCADE
    );''',
    'categories': '''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        is_active INTEGER DEFAULT 1,
        previous_name TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );''',
    'interaction_log': '''CREATE TABLE IF NOT EXISTS interaction_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER,
        document_id INTEGER,
        user_id TEXT,
        event_type TEXT,
        step TEXT,
        content TEXT,
        notes TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );''',
    'document_tags': '''CREATE TABLE IF NOT EXISTS document_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        tag_category TEXT,
        tag_value TEXT,
        llm_source TEXT,
        extraction_confidence REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(document_id, tag_category, tag_value),
        FOREIGN KEY(document_id) REFERENCES single_documents(id) ON DELETE CASCADE
    );''',
    'tag_usage_stats': '''CREATE TABLE IF NOT EXISTS tag_usage_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag_category TEXT,
        tag_value TEXT,
        usage_count INTEGER DEFAULT 0,
        last_used TIMESTAMP
    );'''
}

# Table -> required columns (name -> default DDL fragment to add column if missing)
COLUMN_REQUIREMENTS = {
    'single_documents': {
        'final_category': "ALTER TABLE single_documents ADD COLUMN final_category TEXT",
        'final_filename': "ALTER TABLE single_documents ADD COLUMN final_filename TEXT",
        'searchable_pdf_path': "ALTER TABLE single_documents ADD COLUMN searchable_pdf_path TEXT",
        'ocr_text': "ALTER TABLE single_documents ADD COLUMN ocr_text TEXT",
        'ocr_confidence_avg': "ALTER TABLE single_documents ADD COLUMN ocr_confidence_avg REAL",
        'ai_confidence': "ALTER TABLE single_documents ADD COLUMN ai_confidence REAL",
        'ai_summary': "ALTER TABLE single_documents ADD COLUMN ai_summary TEXT",
        'page_count': "ALTER TABLE single_documents ADD COLUMN page_count INTEGER",
        'file_size_bytes': "ALTER TABLE single_documents ADD COLUMN file_size_bytes INTEGER",
        'status': "ALTER TABLE single_documents ADD COLUMN status TEXT DEFAULT 'pending'",
        'final_category_locked': "ALTER TABLE single_documents ADD COLUMN final_category_locked INTEGER DEFAULT 0",
        'ai_filename_source_hash': "ALTER TABLE single_documents ADD COLUMN ai_filename_source_hash TEXT",
        'ocr_source_signature': "ALTER TABLE single_documents ADD COLUMN ocr_source_signature TEXT"
    },
    'pages': {
        'rotation_angle': "ALTER TABLE pages ADD COLUMN rotation_angle INTEGER DEFAULT 0",
        'human_verified_category': "ALTER TABLE pages ADD COLUMN human_verified_category TEXT",
        'processed_image_path': "ALTER TABLE pages ADD COLUMN processed_image_path TEXT",
        'ocr_text': "ALTER TABLE pages ADD COLUMN ocr_text TEXT"
    },
    'documents': {
        'final_filename_base': "ALTER TABLE documents ADD COLUMN final_filename_base TEXT"
    },
    'batches': {
        'status': "ALTER TABLE batches ADD COLUMN status TEXT",
        'has_been_manipulated': "ALTER TABLE batches ADD COLUMN has_been_manipulated INTEGER DEFAULT 0"
    }
}

READINESS_FEATURES = {
    'single_workflow': ['batches', 'single_documents'],
    'grouped_workflow': ['pages', 'documents', 'document_pages'],
    'categories_ui': ['categories'],
    'tag_extraction': ['document_tags'],
    'rag_similarity': ['document_tags', 'tag_usage_stats'],
    'interaction_logging': ['interaction_log'],
}

def get_db_path() -> Path:
    db_path = os.getenv('DATABASE_PATH')
    if not db_path:
        print("[ERROR] DATABASE_PATH not set (load .env).")
        sys.exit(1)
    return Path(db_path).expanduser().resolve()

def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

def table_exists(cur, name: str) -> bool:
    return cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

def current_columns(cur, table: str) -> set[str]:
    try:
        rows = cur.execute(f"PRAGMA table_info({table})").fetchall()
        return {r[1] for r in rows}
    except sqlite3.Error:
        return set()

def ensure_tables(cur, dry: bool, report: list[str]):
    for name, sql in REQUIRED_TABLES_SQL.items():
        if not table_exists(cur, name):
            report.append(f"CREATE TABLE {name}")
            if not dry:
                cur.execute(sql)
        else:
            report.append(f"OK table {name}")

def ensure_columns(cur, dry: bool, report: list[str]):
    for table, cols in COLUMN_REQUIREMENTS.items():
        existing = current_columns(cur, table)
        if not existing:
            continue  # table missing; creation handled elsewhere or non-critical yet
        for col, ddl in cols.items():
            if col not in existing:
                report.append(f"ADD {table}.{col}")
                if not dry:
                    cur.execute(ddl)
            else:
                report.append(f"OK {table}.{col}")

def summarize_readiness(cur) -> dict:
    existing_tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    summary = {}
    for feature, needed in READINESS_FEATURES.items():
        missing = [t for t in needed if t not in existing_tables]
        summary[feature] = 'ready' if not missing else f"missing: {','.join(missing)}"
    return summary

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='Show actions without applying')
    args = ap.parse_args()

    db_path = get_db_path()
    if not db_path.exists():
        print(f"[ERROR] DB file not found: {db_path}. Use ALLOW_NEW_DB=1 startup first.")
        return 2

    print(f"Upgrading schema for: {db_path}")
    before_size = db_path.stat().st_size
    conn = connect(db_path)
    cur = conn.cursor()

    report: list[str] = []
    ensure_tables(cur, args.dry_run, report)
    ensure_columns(cur, args.dry_run, report)

    if not args.dry_run:
        conn.commit()
    after_size = db_path.stat().st_size

    readiness = summarize_readiness(cur)
    conn.close()

    print("\n=== Actions ===")
    for line in report:
        print(line)
    print("\n=== Feature Readiness ===")
    for feat, status in readiness.items():
        print(f"{feat}: {status}")

    print("\nSize delta: {} -> {} bytes (+{})".format(before_size, after_size, after_size - before_size))
    if args.dry_run:
        print("(dry run: no changes applied)")
    print("Done.")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

# Database Safety & Troubleshooting

This guide explains how the application now protects against accidental SQLite database loss and how to diagnose issues.

## 1. Creation Guard
If the target database file does not exist (or is empty), the app will REFUSE to create it unless one of:
- `ALLOW_NEW_DB=1` (explicit opt‑in) OR
- `FAST_TEST_MODE=1` (test runs)

If neither is set, you'll see a CRITICAL log and a `RuntimeError` on startup. This prevents quietly pointing at the wrong working directory.

## 2. Diagnostics Endpoint
Visit `/admin/db_diagnostics` (or click the "Diagnostics" link in the top banner) to view:
- Absolute path
- Size & last modified timestamp
- Partial SHA256 hash
- Tables and row counts
- Warnings (e.g., minimal schema, missing core tables)

## 3. Template Banner
All pages now display a small banner with:
- Active DB path (resolved absolute)
- File size
- MINIMAL SCHEMA warning if fewer than 6 tables (fresh DB heuristic)
- Link to diagnostics page

## 4. Recovery Script
Use the helper script to find other `.db` files that might contain your historical data:
```
python doc_processor/dev_tools/find_databases.py --search-up 1 --max-depth 5
```
This reports counts for `batches`, `single_documents`, and `documents` tables if present.

## 4b. Upgrade to Full Schema
If your diagnostics show missing tables/columns, run the upgrade script (idempotent):
```
python doc_processor/dev_tools/upgrade_full_schema.py --dry-run   # preview
python doc_processor/dev_tools/upgrade_full_schema.py            # apply
```
Re-run `/admin/db_diagnostics` after applying. The script will report feature readiness for:
- single_workflow
- grouped_workflow
- categories_ui
- tag_extraction / rag_similarity
- interaction_logging

## 5. Hardening Destructive Operations
`reset_environment.py` now requires `CONFIRM_RESET=1` or an interactive 'yes' plus offers `DRY_RUN=1` for safe previews.

Key environment variables:
- `CONFIRM_RESET=1` : Skip prompt and perform irreversible reset.
- `DRY_RUN=1` : Show what would be deleted without modifying anything.

## 6. When You See a Minimal Schema Warning
A minimal schema usually means:
- Brand new database
- Migration scripts not yet run
- You are pointing to the wrong working directory / env

Checklist:
1. Confirm current working directory is repository root.
2. Inspect `DATABASE_PATH` in `.env` or OS env.
3. Run the finder script to look for the original DB.
4. Compare SHA256 partial hash after any copy/move operations.

## 7. Adding / Migrating Tables
Some features (tags, interaction logging) require additional tables (`document_tags`, `interaction_log`, etc.). If they are missing:
- The diagnostics page will still load.
- Related features will degrade gracefully (e.g., no tags returned).
- Run or write migration scripts to create them safely.

## 8. Restoring Categories Only
If you previously backed up custom categories (see `reset_environment.py`), re‑ingest them manually or write a small import script loading `custom_categories_backup.json`.

## 9. Common Issues
| Symptom | Likely Cause | Action |
|---------|--------------|-------|
| Only 3 batches visible; expected more | New empty DB created | Set correct `DATABASE_PATH`; run finder script |
| Guard exception on startup | DB file missing and `ALLOW_NEW_DB` not set | Export `ALLOW_NEW_DB=1` intentionally |
| Tag extraction silent | `document_tags` table missing | Add migration for tag tables |
| Grouped workflow crashes | `documents` / `document_pages` missing | Ensure grouped schema creation path executed |

## 10. Manual Table Creation (Example)
If you need to add the tag tables manually:
```sql
CREATE TABLE IF NOT EXISTS document_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER,
    tag_category TEXT,
    tag_value TEXT,
    llm_source TEXT,
    extraction_confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, tag_category, tag_value),
    FOREIGN KEY(document_id) REFERENCES single_documents(id) ON DELETE CASCADE
);
```

## 11. Verifying Feature Readiness
Feature | Tables Required | Minimal Schema OK? | Notes
--------|-----------------|--------------------|------
Basic single-doc ingestion | batches, single_documents | Yes | Core flow
Rotation persistence | pages (rotation_angle column) | No (needs pages) | Without `pages` rotation cache is limited
Grouped workflow | documents, document_pages, pages | No | Requires page ingestion path
Tag extraction / RAG | document_tags (+ populated single_documents) | No | Tags optional; absence disables feature
Interaction logging | interaction_log | No | Used for analytics / training

If a required table is missing, create it via migration or re-run the feature that auto-creates minimal grouped tables.

## 12. Escalation Playbook
1. Capture diagnostics JSON (copy from `/admin/db_diagnostics`).
2. Hash original DB: `shasum -a 256 path/to/documents.db`.
3. Backup before modifying: `cp documents.db documents.backup.$(date +%s)`.
4. Apply migrations / create missing tables.
5. Re-run diagnostics; confirm row counts consistent.

---
_Last updated: {{ date }}_

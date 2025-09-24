# Changelog

All notable changes to this project will be documented in this file.


## [Unreleased]
- Added full interaction logging: every AI prompt/response, human correction, and status change is now recorded in the `interaction_log` table for RAG and audit
- Database schema and backend updated for robust auditability and future LLM workflows
- Export workflow and documentation improved for clarity and traceability

## [2025-09-24]
### Added
- Category Management UI (`/categories`) with: add, soft delete/restore, rename (tracks previous name), notes field, active/inactive filtering.
- Category change history (`category_change_log`) + drill-down filter (limit & category_id) and integration into `interaction_log` as structured JSON events.
- Optional rename backfill toggle (No backfill) to preserve historical page categories if desired.
- Category sorting (name/id) on management screen with dynamic buttons.
- Batch audit trail view (`/batch_audit/<batch_id>`) surfacing full interaction timeline.
- One-time structured database startup log (JSON) including path, size, mtime, permissions.
- `/update_rotation` endpoint for asynchronous rotation persistence.
- Dynamic primary action button on Verify page (Approve & Next vs Correct & Next) simplifying UX.

### Changed
- `rerun_ocr_on_page` rotation handling: now rotates in-memory only (no permanent file overwrite) preventing double-rotation confusion.
- Verify & Review pages now rely on persisted `rotation_angle` plus client transform—removed destructive image mutation.
- Logging enhancements: category changes and rotation updates recorded as `human_correction` or `category_change` events with JSON payloads.

### Fixed
- Missing Categories nav link layout alignment (converted navbar to flex, removed float issues).
- Rotation persistence gaps causing orientation reset after OCR re-run.
- Nonexistent `/update_rotation` endpoint referenced by UI (now implemented).

### Developer / Schema
- Added new columns to `categories`: `is_active`, `previous_name`, `notes` (idempotent upgrade script logic).
- Added `category_change_log` table for immutable historical events.
- Safe upgrade path via `dev_tools/database_upgrade.py` (re-runnable).

### Notes
- Historical pages retain original categories unless rename backfill selected.
- Interaction log entries now suitable for future RAG / analytics pipelines.

## [2025-09-23]
- Major project cleanup and reorganization.
- Moved all dev/admin scripts to `dev_tools/`.
- Removed obsolete and duplicate files.
- Improved documentation and project structure.

## [Earlier]
- Initial implementation of document processing pipeline.
- Added Flask web interface and SQLite integration.
- Integrated OCR and AI classification.

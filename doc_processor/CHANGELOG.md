# Changelog

All notable changes to this project will be documented in this file.


## [Unreleased]
- Added full interaction logging: every AI prompt/response, human correction, and status change is now recorded in the `interaction_log` table for RAG and audit
- Database schema and backend updated for robust auditability and future LLM workflows
- Export workflow and documentation improved for clarity and traceability

## [2025-09-23]
- Major project cleanup and reorganization.
- Moved all dev/admin scripts to `dev_tools/`.
- Removed obsolete and duplicate files.
- Improved documentation and project structure.

## [Earlier]
- Initial implementation of document processing pipeline.
- Added Flask web interface and SQLite integration.
- Integrated OCR and AI classification.

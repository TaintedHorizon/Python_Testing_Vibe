
# Python_Testing_Vibe: Human-in-the-Loop Document Processing System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This repository contains a robust, RAG-ready document processing pipeline with full auditability, human-in-the-loop verification, and AI integration.

## Key Features

- **End-to-end document pipeline:** Intake → OCR → AI Classification → Human Verification → Grouping → Ordering → Export
- **Full audit trail:** Every AI prompt/response, human correction, rotation update, category change, and status transition is logged (`interaction_log` + `category_change_log`).
- **Category governance:** Add, rename (with historical trace), soft delete/restore, annotate, and optionally backfill old page categories on rename.
- **RAG-ready:** All OCR text, AI outputs, human decisions, and taxonomy evolution are stored for future retrieval-augmented workflows.
- **Export:** Each document is exported as a non-searchable PDF, a searchable PDF (with OCR layer), and a Markdown log (per-document + batch context).
- **Modern Flask web UI** for mission control, verification, review, grouping, ordering, finalization, auditing, and category management.
- **Rotation-safe OCR:** Re-run OCR with an in-memory rotation (non-destructive) while persisting a logical `rotation_angle` for display.
- **Structured logging:** One-time JSON startup database metadata log; structured JSON content for category & rotation events.

## Prerequisites

- Python 3.x
- Git

## Setup

1. Clone this repository to your local machine.
   ```sh
   git clone <your-repository-url>
   cd Python_Testing_Vibe
   ```
2. Create and activate a virtual environment.
   ```sh
   python -m venv venv
   source venv/bin/activate
   ```
3. Install the required dependencies.
   ```sh
   pip install -r requirements.txt
   ```
4. Initialize the database:
   ```sh
   python doc_processor/dev_tools/database_setup.py
   ```
5. Configure `.env` (see `.env.sample` for options)

## Usage

1. Start the Flask server:
   ```sh
   python doc_processor/app.py
   ```
2. Access the UI at `http://localhost:5000`
3. Place test PDFs in your configured INTAKE_DIR
4. Follow the Mission Control workflow for processing, verification, grouping, ordering, and export

### Category Management
Access `/categories` (navbar link). Features include:
- Add new categories with optional notes (LLM guidance / taxonomy context)
- Rename categories (records previous name; optional backfill of historical pages)
- Soft delete (hide) and restore without losing history
- View change history (filter by category id & limit)
- Sort category list by Name or ID

### Verification UX
- Single primary action button dynamically labeled:
   - "Approve & Next" when accepting AI suggestion
   - "Correct & Next" when choosing/modifying/adding a category
- "Flag for Review" preserves page for later attention (category stored as `NEEDS_REVIEW`).

### Rotation & OCR
- Rotate during verification or review (client-side preview).
- Click Confirm Rotation (or persist automatically via AJAX) to store `rotation_angle`.
- Re-run OCR applies rotation in-memory only (original image file left unchanged) preventing cumulative distortion.

### Audit Trail
- Per-batch audit view: `/batch_audit/<batch_id>` lists all interactions chronologically.
- `interaction_log` events include: ai_prompt, ai_response, human_correction, status_change, category_change, rotation_update.
- `category_change_log` is immutable lineage for taxonomy evolution (rename, add, restore, soft_delete) separate from interaction log.

### Schema Evolution
Run upgrades safely:
```sh
python doc_processor/dev_tools/database_upgrade.py
```
Idempotent script adds new columns (`is_active`, `previous_name`, `notes`) & tables (`category_change_log`) as needed.

### Export Artifacts
Each finalized document yields:
- Original / processed PDFs (searchable + non-searchable)
- Markdown metadata / log for traceability
- Category state consistent with latest taxonomy (unless rename backfill skipped)

### Logging Improvements
- On first DB access, a JSON metadata line (path, size, perms, mtime).
- Category and rotation events carry structured JSON payloads for analytics/RAG ingestion.

### Suggested Next Enhancements (Roadmap)
- Schema version table & migration history UI
- Automated rotation auto-save (debounced) removing Confirm button
- Category merge tool for taxonomy consolidation
- Exported JSON bundle for external indexing (vector DB / search)

## Audit & RAG Integration

- All document/page-level OCR text is stored in the database for retrieval
- The `interaction_log` table records every AI and human action, correction, and status change, with batch/document/user/timestamp context
- This enables future LLMs to use Retrieval-Augmented Generation (RAG) with full process history and human feedback

## Contributing

Contributions are welcome! If you'd like to add new features or improve the workflow, feel free to submit a pull request.

## License

This repository is licensed under the MIT License.

## Credits

- @TaintedHorizon (Maintainer)

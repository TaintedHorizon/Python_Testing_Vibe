# Documentation Index

Central index for in-depth subsystem and workflow docs.

## Core Architecture
- `../app.py` – Flask application factory & blueprint registration.
- `LEGACY_CODE.md` – Policy for deprecation, naming, and cleanup.
- `USAGE.md` – (Existing) End-user / operator usage notes.
- `LLM_DETECTION.md` – LLM-based document type detection details.

## Front-End Behavior
- Rotation & scaling unified in `static/js/rotation_utils.js` (see Legacy doc for policy).

## Key Workflows
1. Intake Analysis → Strategy determination (single vs batch)
2. Smart Processing → SSE-driven progress (see `intake_analysis.html` JS section)
3. Manipulation & Verification → Unified iframe PDF rotation layer
4. Export → Final document assembly (service layer)

## Directories of Interest
| Path | Purpose |
|------|---------|
| `doc_processor/routes/` | Blueprint route modules (intake, batch, manipulation, export, admin, api) |
| `doc_processor/services/` | Business logic orchestration (document, batch, export) |
| `doc_processor/static/js/` | Shared front-end utilities (rotation, future UI helpers) |
| `doc_processor/templates/` | Jinja templates (unified rotation system applied) |

## Conventions Snapshot
- Always import configuration: `from config_manager import app_config`
- Database access: `from database import database_connection`
- Rotation state: client-side only + persisted via backend endpoints

## Planned Cleanups
- Rename `manipulate_old.html` → `manipulate_legacy.html` (pending)
- Remove `intake_analysis_new.html` after verifying parity (candidate)

## How to Contribute Docs
1. Place new deep-dive files here (`doc_processor/docs/`).
2. Add an entry above under appropriate section.
3. Link from root README Documentation section.
4. Keep concise; long procedural guides belong in their own file.

_Last updated: October 2025_

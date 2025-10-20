# Architecture & File Map

_Last updated: 2025-10-03_

This document provides a definitive map of the repository structure, categorizes each component (core vs support vs legacy), and explains architectural layering for the `doc_processor` system.

## High-Level Layers

| Layer | Purpose | Key Directories/Files |
|-------|---------|------------------------|
| Entry / Bootstrap | App startup, environment enforcement | `start_app.sh`, `doc_processor/app.py`, `doc_processor/config_manager.py` |
| Routing (Flask Blueprints) | HTTP endpoints grouped by concern | `doc_processor/routes/` |
| Services (Business Logic) | Stateful orchestration independent of HTTP layer | `doc_processor/services/` |
| Processing Engine | OCR, AI, conversion, normalization, rotation, export primitives | `doc_processor/processing.py`, `doc_processor/document_detector.py`, `doc_processor/llm_utils.py` |
| Data Access / Persistence | Database helpers, connection management | `doc_processor/database.py`, `doc_processor/db_utils.py` |
| Domain Utilities | Security, helpers, batch guards, exceptions | `doc_processor/security.py`, `doc_processor/utils/helpers.py`, `doc_processor/batch_guard.py`, `doc_processor/exceptions.py` |
| Presentation | Templating + static assets (PDF.js) | `doc_processor/templates/`, `doc_processor/static/pdfjs/` |
| Runtime State | Mutable workflow directories and DB | `doc_processor/intake/`, `doc_processor/processed/`, `doc_processor/filing_cabinet/`, `doc_processor/logs/`, `doc_processor/documents.db`, `normalized/` |
| Ops / Dev Tools | Maintenance, diagnostics, migration, batch recovery | `doc_processor/dev_tools/` |
| Testing | Automated verification + manual scripts | `doc_processor/tests/`, `tests/`, `doc_processor/test_*` |
| Documentation | Usage, change log, guidance | `README.md`, `doc_processor/readme.md`, `doc_processor/CHANGELOG.md`, `.github/copilot-instructions.md`, `ARCHITECTURE.md` |
| Legacy Archives | Historical implementations (do not modify) | `archive/legacy/Document_Scanner_Gemini_outdated/`, `archive/legacy/Document_Scanner_Ollama_outdated/`, `doc_processor/app_monolithic_backup.py`, `doc_processor/app_original_backup.py` |

## Component Responsibilities

### Entry & Configuration
- `start_app.sh`: Enforces correct startup pattern (activates venv, runs module form, colors + error handling).
- `doc_processor/app.py`: Creates Flask app, registers Blueprints, global filters, logging init, and background threads.
- `doc_processor/config_manager.py`: Typed `AppConfig` object; loads from `.env` and provides canonical values (paths, model config, feature toggles, status constants, normalized cache settings).

### Routing (Blueprints)
| File | Responsibility | Depends On |
|------|----------------|-----------|
| `routes/intake.py` | Intake discovery, AI pre-analysis, rotation persistence | `config_manager`, `document_detector`, `database`, `processing`, `llm_utils` |
| `routes/batch.py` | Smart processing orchestration (SSE), cancellation, batch status | `processing`, `database`, `batch_service`, `config_manager` |
| `routes/manipulation.py` | Verification, grouping, ordering, manipulation UI actions | `document_service`, `processing`, `database` |
| `routes/export.py` | Export workflows, finalization, file serving, PDF viewer | `export_service`, `processing`, `security`, `database` |
| `routes/admin.py` | System diagnostics, logs, maintenance endpoints | `database`, `config_manager` |
| `routes/api.py` | Lightweight AJAX endpoints (renaming, quick status) | `database`, `document_service` |

### Services Layer
Encapsulates procedural steps into composable functions safe for reuse.
- `document_service.py`: Document-level operations (naming, grouping, status transitions).
- `batch_service.py`: Batch creation/resumption, integrity checks, separation logic.
- `export_service.py`: Final assembly, naming policy enforcement, filing cabinet writes.

### Processing & Intelligence
- `processing.py`: Orchestrates OCR pipeline, forced rotation carry-forward, searchable PDF creation, skip-copy optimization, normalization reuse, AI classification fallback flows.
- `document_detector.py`: Multi-point sampling detection (single vs batch scan), image → normalized PDF conversion (hash-based), stale cache GC thread.
- `llm_utils.py`: LLM request wrappers, prompt assembly, context window logging.

### Data Layer
- `database.py`: Connection context manager, CRUD operations, schema reads, status updates.
- `db_utils.py`: Supplemental migrations / consistency helpers.

### Utilities & Cross-Cutting
- `security.py`: Sanitization (`sanitize_filename`), safety checks.
- `utils/helpers.py`: Small shared helpers (pure functions, logging aids, hashing if any not central).
- `batch_guard.py`: Prevents phantom batch recreation on restarts.
- `exceptions.py`: Semantic exception types for clearer upstream handling.

### Presentation
- `templates/`: Unified iframe-based PDF viewing; templates segmented by workflow stage.
- `static/pdfjs/`: Vendored PDF.js for offline, deterministic loading (no CDN dependency).
- `templates/pdf_viewer.html`: Dedicated embedded viewer harness.

### Runtime Directories
| Directory | Ephemeral? | Notes |
|-----------|------------|-------|
| `doc_processor/intake/` | Yes | User places raw docs here. Process then relocates or references. |
| `doc_processor/processed/` | Yes | WIP batch scaffolding, safe to clear if batch not needed (use dev tool). |
| `doc_processor/filing_cabinet/` | Persistent | Final delivered assets. Back up regularly. |
| `doc_processor/archive/` | (Unused) | Currently empty; candidate for removal in cleanup cycle. |
| `doc_processor/logs/` | Rolling | `app.log` plus potential future structured logs. |
| `normalized/` | Rebuildable Cache | SHA-256 keyed normalized PDFs; GC thread prunes stale items. |
| `doc_processor/documents.db` | Persistent | Canonical state + audit trail. WAL/SHM ignored via `.gitignore`. |

### Dev / Ops Tooling
Representative scripts:
- `database_setup.py`: Idempotent schema creation.
- `database_upgrade.py`: Safe additive migrations.
- `reset_environment.py`: Clean slate (intake, processed, DB reset) — CAUTION.
- `diagnose_grouping_block.py`: Investigates grouping-stage deadlocks.
- `cleanup_filing_cabinet_names.py`: Retroactive name normalization.
- `fetch_pdfjs.py`: Vendor / refresh local PDF.js build.
- `rerun_ocr_for_document.py`: Targeted OCR regeneration.

### Testing Strategy
- Unit / light integration: `doc_processor/tests/`.
- Broader or scenario tests: root `tests/`.
- Manual / exploratory scripts: `test_complete_workflow.py`, `test_pdf_conversion.py`.

## E2E Testing (local-first, deterministic)

This project requires reliable, debuggable end-to-end (E2E) tests that exercise both the frontend UX and backend processing for two canonical flows:

- Single-document batches (one document per intake item).
- Grouped/batched scans (multiple documents scanned together and grouped into a batch).

The following guidance is the authoritative source for adding, running, and debugging E2E tests locally. Follow it exactly when implementing or stabilizing tests.

Environment & conventions
- Use the repository venv located at `doc_processor/venv`.
- Always start the application with the root `./start_app.sh` script (it activates the correct venv and launches the Flask app with the right working directory).
- Tests that run Playwright must be gated using the environment variable `PLAYWRIGHT_E2E=1`.
- Tests that rely on deterministic, test-only behavior (skipping heavy OCR/LLM and exposing debug endpoints) must use `FAST_TEST_MODE=1` in the environment.

Test-only debug endpoints
- Implement test-only endpoints only under `routes/*` and guard them so they are only active during `FAST_TEST_MODE` or when requests come from `localhost`.
- Recommended debug endpoints (example names already used elsewhere in this repo):
	- `/batch/api/debug/latest_document` — returns the most recently created single-document row (id, batch_id, filename).
	- `/batch/api/debug/batch_documents/<batch_id>` — returns `single_documents` and grouped documents for a batch.
- Tests should prefer querying these endpoints for canonical document ids or batch ids rather than relying on brittle UI click chains.

Artifact collection and diagnostics
- All E2E tests must dump artifacts on failure to `doc_processor/tests/e2e/artifacts/` including:
	- full-page HTML snapshot (`.html`) for DOM inspection,
	- full-page screenshot (`.png`),
	- tail of app process log (`app_process.log`) captured when the app is started by the test harness.
- Tests should also save any debug API responses (JSON) that helped the test make deterministic navigation choices.

How to run individual tests locally (recommended)
1. Activate the venv and start the app from the repo root:
```bash
cd /home/svc-scan/Python_Testing_Vibe
source doc_processor/venv/bin/activate
./start_app.sh
```
2. In another terminal run the test you want with the flags set:
```bash
cd /home/svc-scan/Python_Testing_Vibe
source doc_processor/venv/bin/activate
FAST_TEST_MODE=1 PLAYWRIGHT_E2E=1 pytest -q doc_processor/tests/e2e/<test_file>::<test_name>
```

Acceptance criteria for test success
- The test completes with exit code 0 under the given environment flags.
- Artifacts are produced under `doc_processor/tests/e2e/artifacts/` when a failure or assertion occurs.
- Backend analysis and batch creation steps are verified via the debug endpoints or app logs (look for `Document analysis SUCCESS` and `Created new processing batch <id>` messages in the app log).

Design notes and best practices
- Prefer server-driven navigation: kick off analysis via the normal intake route, poll analysis status endpoints or call `/batch/process_smart` and use debug endpoints to obtain the canonical `document_id` and `batch_id`. Use those ids to navigate directly to the manipulation or preview routes (e.g., `/manipulation/<batch_id>` or `/document/<id>/manipulate`).
- Use robust selectors: target stable attributes such as `data-testid`, `id` attributes rendered only in `FAST_TEST_MODE`, or canonical route URLs embedded in anchor hrefs. Avoid relying solely on visual class names which are more likely to change.
- Wait for DOM attachment over visibility when dealing with modals or rapidly updated widgets. Favor `attached`/`present` waits then assert visibility if necessary.
- Keep timeouts conservative but reasonable for CI-less local runs: default to 10–20s for heavy backend operations when `FAST_TEST_MODE` is not set; tests running under `FAST_TEST_MODE` may use shorter timeouts because heavy processing is skipped.

Where to put tests and helpers
- Tests: `doc_processor/tests/e2e/` (pytest-playwright style). Name tests descriptively: `test_single_batch_flow.py`, `test_group_batch_flow.py`.
- Helpers: `doc_processor/tests/e2e/playwright_helpers.py` — provide fixtures to start/stop the app, copy intake fixtures, poll debug endpoints, and dump artifacts on failure.

Stabilization checklist (when a test flakes)
1. Collect artifacts (HTML, PNG, app log) and debug endpoint JSON output.
2. Inspect app log for `Document analysis SUCCESS` and batch creation entries.
3. If backend processed but UI link was not present, widen selectors or prefer direct navigation using ids from debug endpoints.
4. Add a test-only `data-testid` attribute guarded by `FAST_TEST_MODE` for particularly brittle anchors if necessary.

If you change routes or templates that tests rely on, update this E2E Testing section and any helpers in `doc_processor/tests/e2e/` immediately.

## Dependency Flow (Simplified)
```
[ config_manager ] ---> consumed by all layers needing configuration
[ routes/* ] -----> call into [ services/* ] & [ processing ] & [ database ]
[ services/* ] ---> orchestrate calls to [ processing ] + [ database ]
[ processing ] ---> uses [ llm_utils ], OCR libs, filesystem, [ database ] selectively
[ document_detector ] --> feeder for intake & processing reuse path
[ export_service ] ---> uses [ security ], filesystem ops
```

No cyclic dependencies: each layer only depends downward.

## Legacy / Cleanup Candidates
| Item | Rationale | Action Plan |
|------|-----------|------------|
| (removed legacy backups) | Cleaned up | Backups & duplicate license removed in cleanup pass |
| `doc_processor/archive/` | Empty & unused | Remove after validating no planned workflow usage |
| Legacy directories (`Document_Scanner_*_outdated/`) | Replaced by modular architecture | Keep until external docs no longer reference them |

## Architectural Principles
1. Idempotent Processing: Cache normalization + rotation persistence eliminate redundant compute.
2. Deterministic Startup: Single entry script prevents "works on my machine" drift.
3. Clear Layering: Routes never implement heavy logic; services and processing handle complexity.
4. Fail-Safe Exports: Filenames sanitized + duplicate detection before overwrite.
5. Observability: Emoji-tagged logs & SSE progress for user feedback.
6. Isolation: Vendored PDF.js avoids external availability risk.
7. Rebuildable State: Cached/derived assets (normalized PDFs) can be purged without data loss.

## Future Enhancements (Backlog Suggestions)
- Add `/admin/cache_stats` endpoint exposing normalization cache hit/miss counts.
- Introduce feature flags section in `config_manager.py` for experimental toggles.
- Add structured logging (JSON lines) for machine parsing.
- Implement test coverage reporting (pytest-cov) and badge.
- Consider moving dev tools that mutate data behind an authenticated admin route.

## FAQ
**Q: Why is the normalized cache outside `doc_processor/`?**  
A: To emphasize rebuildable/non-source nature and allow potential reuse by sibling packages later.

**Q: Can I delete `normalized/`?**  
Yes. It will be lazily rebuilt; only performance (not correctness) is impacted.

**Q: How do I safely purge a stuck batch?**  
Use `dev_tools/force_reset_batch.py` then optionally `reset_environment.py` if a full reset is desired.

---
If you update structure or add modules, please update this file and the file map section in `README.md`.

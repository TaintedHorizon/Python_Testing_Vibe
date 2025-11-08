% Software Requirements Specification (SRS)

Version: 0.1
Author: Automated draft (please review & complete)
Date: 2025-11-04

Purpose
-------
This document is a living Software Requirements Specification (SRS) draft for the
Python_Testing_Vibe repository, with primary focus on the `doc_processor` application
and repository-level CI/automation standards. It is intended to capture functional
and non-functional requirements, interfaces, acceptance criteria, and traceability
to tests and CI workflows. Use this file as the authoritative starting point and
update sections marked TODO with precise values and acceptance thresholds.

Scope
-----
This SRS covers:

- The `doc_processor` human-in-the-loop document processing system (intake → OCR/AI → verification → export).
- Repository-level CI, validator workflows, and helper scripts under `.github/` that enforce repository hygiene.
- Test harnesses and E2E flows (Playwright-based UI tests and pytest-based unit/integration tests).

Definitions & Abbreviations
-------------------------
- SRS: Software Requirements Specification
- CI: Continuous Integration (GitHub Actions)
- E2E: End-to-end
- LLM: Large Language Model (Ollama in this repo)
- FAST_TEST_MODE: configuration flag used to shorten/skip heavy processing in tests

1. Overall description
----------------------

1.1 System context

The system ingests user documents (images, PDFs), runs OCR, performs AI classification,
provides a UI for human verification, groups/exports documents, and stores processed
output in a filing cabinet directory. The system integrates with external services:
Ollama (LLM), Tesseract (OCR), PDF tooling (poppler), and GitHub Actions (CI).

1.2 Major actors

- Human user (operator) — uploads documents, verifies AI suggestions, groups/exports.
- Admin/maintainer — configures CI, branch protection, and runs maintenance scripts.
- CI system (GitHub Actions) — validates workflow YAML and runs tests and smoke jobs.

2. Functional requirements
--------------------------

Each functional requirement is numbered for traceability.

FR-1 Intake and storage
- FR-1.1 The system SHALL accept uploaded files (images, PDFs) into `doc_processor/intake/`.
- FR-1.2 The system SHALL normalize images into PDF and store normalized copies in `normalized/` (hash-based dedupe).

FR-2 OCR and text extraction
- FR-2.1 The system SHALL run OCR (EasyOCR/Tesseract) on documents and persist extracted text.
- FR-2.2 The system SHALL respect rotation metadata and apply rotation before OCR.

FR-3 AI classification and filename suggestion
- FR-3.1 The system SHALL call `llm_utils.get_ai_document_type_analysis` (Ollama endpoint) to classify documents and suggest filenames.
- FR-3.2 The system SHALL persist AI suggestions and allow human overrides.

FR-4 Human verification and grouping
- FR-4.1 The web UI SHALL display AI suggestions per document and allow edits.
- FR-4.2 The UI SHALL support drag-and-drop grouping and ordering within a batch.

FR-5 Export and filing
- FR-5.1 The system SHALL assemble grouped documents into exportable PDFs and store them in `doc_processor/filing_cabinet/`.
- FR-5.2 The system SHALL provide routes to serve PDFs and preview templates.

FR-6 Administration and safety
- FR-6.1 The system SHALL provide dev_tools scripts for DB setup and migrations (see `doc_processor/dev_tools/`).
- FR-6.2 The repository SHALL include a validator workflow that blocks malformed workflow YAML from merging to `main` (see `.github/workflows/validate-workflows.yml`).

3. Non-functional requirements
------------------------------

NFR-1 Performance
- NFR-1.1 Typical OCR throughput on CI test hardware: TBD. (TODO: set target pages/min)

NFR-2 Reliability
- NFR-2.1 The system SHALL provide FAST_TEST_MODE for deterministic test runs that avoid long OCR/LLM calls.

NFR-3 Security
- NFR-3.1 Filenames and served paths SHALL be sanitized to avoid path traversal (see `doc_processor/security.py`).
- NFR-3.2 Secrets for Ollama and other services SHALL be stored in GitHub Secrets for CI and in `.env` locally.

NFR-4 Testability
- NFR-4.1 E2E tests SHALL run locally via `./scripts/run_local_e2e.sh` and in CI via `.github/workflows/playwright-e2e.yml`.

4. External interfaces
-----------------------

4.1 Ollama LLM
- Endpoint: configured via `config_manager` (`OLLAMA_HOST`, `OLLAMA_MODEL`).
- Contract: `get_ai_document_type_analysis(file_path, ...)` returns classification and filename suggestions.

4.2 GitHub Actions (CI)
- Validator workflow: `.github/workflows/validate-workflows.yml` must run on PRs and be configured as a required check on `main`.
- Artifact uploads must include matrix values to avoid duplicate artifact name collisions.

5. Data requirements
---------------------

- DB schema: primary runtime DB is SQLite at `doc_processor/documents.db` (git-ignored). See `doc_processor/dev_tools/database_setup.py` for schema setup.
- Persistent directories: `intake/`, `processed/`, `filing_cabinet/`, `normalized/`, `logs/`.

6. Acceptance criteria & test cases
-----------------------------------

AC-1 Validator
- AC-1.1 The `validate-workflows` workflow SHALL pass for every push to `main` (unless a workflow file contains an intentional syntax error).
- AC-1.2 Enabling the validator as a required status check SHALL block merging when workflow YAMLs are invalid.

AC-2 CI fast-path
- AC-2.1 The `ci-fast-path` workflow SHALL install only `doc_processor/requirements-ci.txt` and complete within X minutes on CI runners. (TODO: set X)

AC-3 E2E
- AC-3.1 The Playwright E2E suite SHALL pass in CI on a scheduled or manual run within Y minutes. (TODO: set Y)

7. Traceability matrix (example)
--------------------------------

| Requirement | CI/Test | Notes |
|-------------|---------|-------|
| FR-2 OCR    | unit tests / integration | see `doc_processor/tests` |
| FR-3 AI     | integration / mocked LLM | use `FAST_TEST_MODE` for deterministic runs |

8. Operational procedures & rollback
------------------------------------

8.1 Branch protection change rollback
- Before changing branch protection, run `gh api /repos/<owner>/<repo>/branches/<branch>/protection` and save the response to a file as the backup.
- To revert, construct a minimal payload from the backup and `PUT` it back via `gh api --method PUT`.

8.2 CI incident playbook (brief)
- Step 1: Identify failing runs with `gh run list` and `gh run view <id> --log`.
- Step 2: If validator blocks merges with false positives, run the validator locally and fix the failing YAML files or temporarily remove the required check while fixes land.

9. Open issues and TODOs
------------------------

- TODO: Define numeric acceptance criteria (X minutes, Y minutes targets for CI/E2E).
- TODO: Add a trace matrix rows for all critical requirements mapping to tests and docs.
- TODO: Add a schematic system context diagram (image or markdown ASCII).

Appendix A — relevant files & links
----------------------------------
- `.github/workflows/validate-workflows.yml` — workflow validator
- `.github/scripts/validate_workflow.py` — YAML validator script
- `.github/scripts/add_required_check.sh` — branch-protection helper (supports --dry-run)
- `.github/scripts/poll_run.sh` — polling helper
- `doc_processor/docs/REQUIREMENTS.md` — dependency documentation
- `doc_processor/readme.md` — application-level documentation

Appendix B — change log for this SRS draft
------------------------------------------
- 0.1 (2025-11-04) — initial automated draft created; TODOs inserted for human validation and numeric targets.

Please review the TODO items above and provide the missing numeric targets/acceptance criteria and any additional functional requirements to include. After review I can update this file and open a PR for team review.

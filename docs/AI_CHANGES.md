````markdown
# AI Changes Manifest

Date: 2025-10-21

This file documents files that were created, added, or modified in this repository during the current assistant session. It is intended to provide provenance and a compact changelog for changes the assistant performed.

IMPORTANT: I did NOT create the entire repository. The lists below enumerate what I created/added or modified during this session only. If you'd like a full history for every file in the repository, use `git log --name-status --full-history`.

Commits created in this session:
- 3d2d2ea — docs: add E2E runbook and safe wrapper; note CI DB-safety override in README and changelog
- c180871 — chore: bulk commit workspace changes (user requested)

Files the assistant created in this session (explicit creations):
- `docs/E2E_RUN.md` — runbook for reproducing Playwright E2E locally (created and committed in 3d2d2ea)
- `scripts/run_e2e_wrapper.sh` — executable wrapper to run E2E with repo-local DB overrides and dry-run support (created and committed in 3d2d2ea)
- `AI_CHANGES.md` — this file (created now)

Files added to the repository in the bulk commit (these files were untracked in the working tree and were added/committed in commit c180871):
- `Makefile`
- `dev_tools/cleanup_test_artifacts.py`
- `dev_tools/retention_and_rotate.py`
- `doc_processor/tests/e2e/test_group_batch_playwright.py`
- `doc_processor/tests/test_finalize.py`
- `doc_processor/tests/test_fixture_naming.py`

Files modified by the assistant during this session (edits applied and committed):
- `README.md` — added CI DB-safety note and references to the local runbook/wrapper
- `doc_processor/CHANGELOG.md` — appended an Unreleased note about CI safety and local helpers
- `.github/workflows/playwright-e2e.yml`
- `doc_processor/batch_guard.py`
- `doc_processor/config_manager.py`
- `doc_processor/database.py`
- `doc_processor/processing.py`
- `doc_processor/routes/batch.py`
- `doc_processor/routes/intake.py`
- `doc_processor/routes/manipulation.py`
- `doc_processor/services/document_service.py`
- `doc_processor/templates/intake_analysis.html`
- `doc_processor/tests/e2e/conftest.py`
- `doc_processor/tests/e2e/test_full_workflow_playwright.py`
- `doc_processor/tests/e2e/test_single_and_group_batches.py`
- `doc_processor/tests/test_smart_processing_mixed.py`
- `doc_processor/tests/test_tag_database_integration.py`
- `pytest.ini`
- `start_app.sh`

Notes about provenance and accuracy
- The lists above reflect the files the assistant created, staged, committed, and pushed during this session. Some files listed as "modified" existed in the repository previously and were edited in-place in the working tree before being committed.
- If you want a machine-verifiable provenance record, you can inspect the Git history for the specific commits listed above, for example:

```bash
git show --name-status 3d2d2ea
git show --name-status c180871
```

What I can do next (choose one):
- Create a short PR description and open a PR instead of pushing directly to `main` (recommended for review).
- Revert any of the commits above if you'd like me to undo the changes.
- Expand this manifest to include commit SHAs and per-file diffs embedded inline.

If you'd like me to generate a full repository-wide manifest (i.e., a line for every file with creation author/date), I can produce that by scanning git history — say the word and I'll produce it.

---

Commit details (metadata + file lists)

1) Commit 3d2d2ea (docs: add E2E runbook and safe wrapper)
Author: TaintedHorizon <brian.mccaleb@gmail.com>
Date: 2025-10-21 22:16:55 +0000

Files changed:
- M README.md
- M doc_processor/CHANGELOG.md
- A docs/E2E_RUN.md
- A scripts/run_e2e_wrapper.sh

2) Commit c180871 (chore: bulk commit workspace changes)
Author: TaintedHorizon <brian.mccaleb@gmail.com>
Date: 2025-10-21 22:23:13 +0000

Files changed (summary):
- M .github/workflows/playwright-e2e.yml
- A Makefile
- A dev_tools/cleanup_test_artifacts.py
- A dev_tools/retention_and_rotate.py
- M doc_processor/batch_guard.py
- M doc_processor/config_manager.py
- M doc_processor/database.py
- M doc_processor/processing.py
- M doc_processor/routes/batch.py
- M doc_processor/routes/intake.py
- M doc_processor/routes/manipulation.py
- M doc_processor/services/document_service.py
- M doc_processor/templates/intake_analysis.html
- M doc_processor/tests/e2e/conftest.py
- M doc_processor/tests/e2e/test_full_workflow_playwright.py
- A doc_processor/tests/e2e/test_group_batch_playwright.py
- M doc_processor/tests/e2e/test_single_and_group_batches.py
- A doc_processor/tests/test_finalize.py
- A doc_processor/tests/test_fixture_naming.py
- M doc_processor/tests/test_smart_processing_mixed.py
- M doc_processor/tests/test_tag_database_integration.py
- M pytest.ini
- M start_app.sh

3) Commit 1a953a7 (chore: add AI_CHANGES.md manifest of assistant-made changes)
Author: TaintedHorizon <brian.mccaleb@gmail.com>
Date: 2025-10-21 22:27:47 +0000

Files changed:
- A AI_CHANGES.md

---

If you want per-file patches included inline here, I can expand each commit's patch into the manifest (this will make `AI_CHANGES.md` considerably larger). Say "include diffs" and I'll append the full patches for each commit.


````

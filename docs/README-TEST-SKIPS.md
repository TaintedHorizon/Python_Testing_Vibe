# Test / Static Audit Skip Notes

Date: 2025-10-24

Summary
-------
As part of the output-path audit and test hardening work, entries that are test artifacts or static asset bundles were intentionally recorded as "skipped/test/static" in the previous audit pass.

This file documents those decisions so future auditors and contributors understand why these paths were not wrapped or changed to the `select_tmp_dir()` flow during the dry-run wrapping.

Files considered skipped
----------------------
The following files are the primary candidates that were considered test artifacts or static assets and treated as "skipped/test/static" for the purposes of the dry-run rollout and audit:

```
doc_processor/static/pdfjs/pdf.worker.min.js
doc_processor/static/pdfjs/pdf.min.js
```

The following test-related files and generated e2e artifacts were considered test-only and recorded as skipped:

```
doc_processor/tests/test_manipulation_autosave.py
doc_processor/tests/test_finalize.py
doc_processor/tests/conftest.py
doc_processor/tests/test_retention_guard.py
doc_processor/tests/test_tag_database_integration.py
doc_processor/tests/test_single_export.py
doc_processor/tests/test_grouped_rotation.py
doc_processor/tests/test_finalize_normalization.py
doc_processor/tests/test_batch_guard.py
doc_processor/tests/test_rescan_document.py
doc_processor/tests/test_complete_workflow.py
doc_processor/tests/test_rotation_serving.py
doc_processor/tests/test_intake_to_single_document.py
doc_processor/tests/test_cached_searchable.py
doc_processor/tests/test_image_support.py
doc_processor/tests/test_gui_inprocess.py
doc_processor/tests/test_smart_processing_mixed.py
doc_processor/tests/test_ocr_cache_invalidation.py
doc_processor/tests/test_manipulation.py
doc_processor/tests/test_db_backup.py

# E2E / playwright / artifacts
doc_processor/tests/e2e/test_preview_rotate_persist.py
doc_processor/tests/e2e/conftest.py
doc_processor/tests/e2e/test_sse_ui.py
doc_processor/tests/e2e/test_single_and_group_batches.py
doc_processor/tests/e2e/test_full_workflow_playwright.py
doc_processor/tests/e2e/test_group_batch_playwright.py
doc_processor/tests/e2e/test_gui_end_to_end_playwright.py
doc_processor/tests/e2e/test_process_single_documents_playwright_full.py
doc_processor/tests/e2e/playwright_helpers.py
doc_processor/tests/e2e/artifacts/*.html
```

Rationale
---------
- Test files normally write transient artifacts during runs (HTML artifacts, temp PDFs, PID files). These belong to CI/test infrastructure and should be handled by the test harness (pytest tmp_path / TEST_TMPDIR) rather than repo-wide rewrites.
- Static bundles (e.g., pdfjs) are asset files that are not runtime outputs from application code; they are allowed to remain as static files in `doc_processor/static/` and may be downloaded or written by dev scripts. For CI, `PDFJS_DEST` can be used to override their destination.

Notes and next steps
--------------------
- If you want these entries to include `"status": "skipped/test/static"` inside `docs/output_path_audit.json`, I can reapply those status fields programmatically (or update the audit generator to add them for matching patterns) — say the word `annotate` and I'll add the status field to the JSON file.
- If you'd like a narrower set (only e2e artifacts or only pdfjs) to remain skipped while other test outputs are wrapped, tell me which scope to keep.

Maintainer: automated audit on branch `chore/wrap-devtools-batch-11` (2025-10-24)

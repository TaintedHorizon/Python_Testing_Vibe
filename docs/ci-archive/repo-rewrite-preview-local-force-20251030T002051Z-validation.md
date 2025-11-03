# Validation: repo-rewrite-preview-local-force-20251030T002051Z

Preview tarball: `ci_artifacts/repo-rewrite-preview-local-force-20251030T002051Z.tar.gz`

SHA256: 2f1674f108f8fd21a8e038864ff2cbc32d06899986fc2dfd79ffa68538801ffb

Date: 2025-10-30T00:20Z (local validation run)

Summary
-------
- Smoke validation performed by extracting the preview mirror, checking out a working copy, and running two deterministic e2e smoke checks against a minimal HTTP server.
- Commands used (high level):
  - Extract preview: `tar -xzf ci_artifacts/repo-rewrite-preview-local-force-20251030T002051Z.tar.gz -C /tmp/rewrite_preview`
  - Create checkout: `git clone /tmp/rewrite_preview/repo-mirror.git /tmp/rewrite_preview/checkout`
  - Start minimal HTTP server serving `/tmp/rewrite_preview/www/index.html` on port 5000
  - Run tests using repo venv: `PLAYWRIGHT_E2E=1 E2E_URL=http://127.0.0.1:5000/ doc_processor/venv/bin/python -m pytest ...`

Results
-------
- `doc_processor/tests/e2e/test_health.py::test_root_health` -> PASS
- `doc_processor/tests/e2e/test_root_content.py::test_root_contains_title` -> PASS

Notes
-----
- This was a smoke-level validation. It does not replace running the full CI matrix or heavy-deps consumer validation. The next step is to run the full test matrix (including the heavy consumer validation) on the rewritten checkout in a controlled runner (recommended: GitHub Actions runner using Python 3.11 or a local container matching CI).

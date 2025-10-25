E2E Pipeline (Playwright + Pytest)
===================================

Purpose
-------
This document describes the E2E pipeline scaffold added to `.github/workflows/e2e.yml`.
The workflow is intentionally manual (workflow_dispatch) and can be triggered for pull requests by adding the label `run-e2e` to a PR.

What it does
-----------
- Checks out the repo
- Sets up Python 3.12 and Node.js 20
- Installs Python requirements from `doc_processor/requirements.txt`
- Installs Playwright and browsers
- Sets `TEST_TMPDIR=/tmp/python_testing_vibe_e2e` for the job
- Runs pytest against `doc_processor/tests/e2e`
- Uploads `doc_processor/tests/e2e/artifacts` and the job `TEST_TMPDIR` contents as artifacts

Notes and next steps
-------------------
- Adjust the `pytest` invocation if your E2E tests are run via `playwright test` or under different markers.
- You may want to add a dedicated runner with larger resource limits if the tests are heavy.
- Secure artifact storage: the workflow uploads artifacts to GitHub Actions storage; for long-term retention use a cloud bucket.

Triggering
---------
- Manually via the Actions UI (workflow_dispatch)
- On PRs by adding the `run-e2e` label (the workflow checks for that label)

Safety
-----
The workflow sets `TEST_TMPDIR` to an external `/tmp` path and does not write into the repository root. Ensure CI secrets and infrastructure are configured before enabling automatic runs on all PRs.

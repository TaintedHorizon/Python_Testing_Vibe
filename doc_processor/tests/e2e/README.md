# Playwright E2E tests

This folder contains Playwright-based end-to-end tests that exercise the full GUI workflow (intake → analyze → smart processing → manipulate → export).

Artifacts
- On local runs the artifacts will be written to `doc_processor/tests/e2e/artifacts/` by default.
- You can override the location using the `E2E_ARTIFACTS_DIR` environment variable.
- On failure the following artifacts are saved per-test: full-page PNG screenshot, page HTML, and the application `app_process.log` captured from the server process.

Running locally
1. Create and activate the venv in `doc_processor/`:

```bash
cd doc_processor
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install playwright pytest-playwright
python -m playwright install --with-deps
```

2. Run the E2E test(s):

```bash
# from repo root
FAST_TEST_MODE=1 SKIP_OLLAMA=1 PLAYWRIGHT_E2E=1 pytest -q doc_processor/tests/e2e
```

3. Inspect artifacts (if any) in `doc_processor/tests/e2e/artifacts/`.

CI
- The GitHub Actions workflow `.github/workflows/playwright-e2e.yml` sets `E2E_ARTIFACTS_DIR` to the runner workspace path and uploads artifacts as a job artifact after the test run completes (success or failure).

Playwright E2E test scaffold

This folder contains a scaffold E2E test for the intake -> smart processing -> batch audit flow.

The test is skipped by default. To run it locally:

1. Install Python Playwright and browsers:

   python -m pip install playwright pytest-playwright
   python -m playwright install

2. Ensure the app can be started with the repository startup script from the repo root:

   ./start_app.sh

3. Ensure the intake directory contains the sample PDF used by the tests:

   cp doc_processor/tests/fixtures/sample_small.pdf $(python -c "from config_manager import app_config; print(app_config.INTAKE_DIR)")

4. Run the test (enable it via env var):

   PLAYWRIGHT_E2E=1 pytest -q doc_processor/tests/e2e/test_process_single_documents_e2e_playwright.py

Notes:
- The scaffold test is intentionally conservative. Implementing a robust Playwright test requires
  handling the background app process lifecycle, waiting for SSE-based updates (or polling the
  `/batch/api/smart_processing_progress` endpoint), and possibly adjusting timeouts for slower
  CI environments.
- If you'd like, I can implement the full Playwright interactions and manage the app process
  lifecycle inside the test (start/stop). Tell me and I'll implement it next.

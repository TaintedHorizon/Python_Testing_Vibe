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

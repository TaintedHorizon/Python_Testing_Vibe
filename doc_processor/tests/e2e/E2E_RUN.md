Quick run instructions for Playwright E2E tests

Prerequisites (local):

1. Activate the project's venv inside `doc_processor`:

   cd doc_processor
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

2. Install Playwright for Python and browsers:

   pip install playwright pytest-playwright
   python -m playwright install

3. Start the app (from repo root):

   ./start_app.sh

4. Run the specific E2E test (enable by env var):

   PLAYWRIGHT_E2E=1 pytest -q doc_processor/tests/e2e/test_process_single_documents_playwright_full.py

Notes:
- The test will copy `doc_processor/tests/fixtures/sample_small.pdf` into your configured intake directory.
- The test runs headless by default. For debugging, change `headless=True` to `headless=False` in the test.
- Adjust timeouts if your machine is slow or Playwright browsers are downloading on first use.

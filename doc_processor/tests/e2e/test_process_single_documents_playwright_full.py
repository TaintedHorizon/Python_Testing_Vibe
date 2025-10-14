import os
import subprocess
import time
import signal
import requests
import pytest

PLAYWRIGHT_FLAG = os.getenv('PLAYWRIGHT_E2E', '0')


@pytest.mark.skipif(PLAYWRIGHT_FLAG != '1', reason='Playwright E2E disabled by default')
def test_playwright_intake_to_single_documents(tmp_path):
    """Full Playwright E2E: intake -> analyze -> smart -> verify single_documents.

    Requirements (local):
      - Playwright Python package installed: `pip install playwright pytest-playwright`
      - Playwright browsers installed: `python -m playwright install`
      - A working virtualenv (repo's `./start_app.sh` handles this)

    The test uses a background process to start the app via `./start_app.sh` from repo root,
    then controls a browser to exercise the UI. It attempts to be robust with timeouts
    and will clean up the spawned process on completion.
    """

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    start_script = os.path.join(repo_root, 'start_app.sh')
    assert os.path.exists(start_script), f'start_app.sh not found at {start_script}'

    # Copy sample pdf into intake directory used by the app
    from config_manager import app_config
    sample_pdf = os.path.join(os.path.dirname(__file__), 'fixtures', 'sample_small.pdf')
    intake_dir = app_config.INTAKE_DIR
    os.makedirs(intake_dir, exist_ok=True)
    dest_pdf = os.path.join(intake_dir, os.path.basename(sample_pdf))
    if not os.path.exists(dest_pdf):
        import shutil
        shutil.copy2(sample_pdf, dest_pdf)

    # Start the app in background
    proc = subprocess.Popen([start_script], cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, preexec_fn=os.setsid)

    try:
        # Wait for app to be healthy
        health_url = 'http://127.0.0.1:5000/api/system_info'
        timeout = time.time() + 60
        healthy = False
        while time.time() < timeout:
            try:
                r = requests.get(health_url, timeout=2)
                if r.status_code == 200:
                    healthy = True
                    break
            except Exception:
                pass
            time.sleep(1)
        assert healthy, 'App did not become healthy in time'

        # Import Playwright here to fail early if not installed
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # Navigate to intake analysis page
            page.goto('http://127.0.0.1:5000/intake/analyze_intake')

            # Click Start Analysis button (uses onclick startAnalysis)
            page.wait_for_selector('button:has-text("Start Analysis")', timeout=10000)
            page.click('button:has-text("Start Analysis")')

            # Wait for the analysis to complete; server triggers a success notification
            # We'll wait for the success notification or for the loading-state to hide
            page.wait_for_timeout(2000)

            # Poll until the analysis cache file exists or until analyses appear in DOM
            analysis_done = False
            for _ in range(60):
                try:
                    # Attempt to detect analysis summary presence in DOM
                    if page.query_selector('.document-section'):
                        analysis_done = True
                        break
                except Exception:
                    pass
                time.sleep(1)
            assert analysis_done, 'Analysis did not produce DOM results in time'

            # Click Start Smart Processing button
            page.click('button:has-text("Start Smart Processing")')

            # Wait for smart progress panel to appear and complete
            page.wait_for_selector('#smart-progress-panel', timeout=10000)

            # Wait for the result batches area to populate (smart-batch-ids)
            smart_complete = False
            for _ in range(120):
                try:
                    el = page.query_selector('#smart-batch-ids')
                    if el and el.is_visible():
                        html = el.inner_text()
                        if 'Single Docs' in html or '#' in html:
                            smart_complete = True
                            break
                except Exception:
                    pass
                time.sleep(1)
            assert smart_complete, 'Smart processing did not complete or produce batch IDs in time'

            # If we have a single batch link, navigate to it (extract first href)
            batch_link = page.query_selector('#smart-batch-ids a')
            if batch_link:
                href = batch_link.get_attribute('href')
                page.goto(f'http://127.0.0.1:5000{href}')
            else:
                page.goto('http://127.0.0.1:5000/batch/control')

            # Look for document rows in the audit view
            doc_present = False
            for _ in range(30):
                try:
                    if page.query_selector('table') and page.query_selector('table tr'):
                        doc_present = True
                        break
                except Exception:
                    pass
                time.sleep(1)
            assert doc_present, 'No documents visible in batch audit/control'

            # Cleanup playwright resources
            context.close()
            browser.close()

    finally:
        # Stop the background app
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass

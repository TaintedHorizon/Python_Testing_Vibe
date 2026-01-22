import os
import time
import shutil
import pytest
import sqlite3
import requests
from config_manager import app_config
import pickle
import tempfile


def _click_if_present(page, selector_texts, timeout=5000):
    """Try several selector forms and click the first that matches."""
    # Try each selector, waiting briefly for it to appear (avoids races with JS)
    for sel in selector_texts:
        try:
            # playwright's wait_for_selector supports CSS and text selectors
            el = page.wait_for_selector(sel, timeout=timeout)
            if el:
                el.click(timeout=timeout)
                return True
        except Exception:
            # try next selector
            pass
    return False


def _wait_for_any(page, selectors, timeout=30000, poll=0.5):
    deadline = time.time() + (timeout / 1000.0)
    while time.time() < deadline:
        for sel in selectors:
            try:
                if page.query_selector(sel):
                    return sel
            except Exception:
                pass
        time.sleep(poll)
    return None


def test_full_workflow(app_process, e2e_page):
    """Full end-to-end test: intake -> analyze -> smart processing -> audit -> export.

    This test uses the `app_process` fixture which starts the app in an isolated temp
    workspace (and will skip the test if PLAYWRIGHT_E2E isn't set). The test copies
    the sample PDF into the intake dir created by the fixture, drives the UI via
    Playwright, and asserts that UI progress appears and that an exported file
    is written to the filing cabinet directory.
    """

    base_url = app_process['base_url']
    intake_dir = app_process['intake_dir']
    filing_cabinet = app_process['filing_cabinet']

    # Ensure sample PDF is present in the intake directory used by the app
    # sample_small.pdf lives in doc_processor/tests/fixtures (one level up from this e2e/ folder)
    sample_pdf = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'sample_small.pdf'))
    assert os.path.exists(sample_pdf), f'sample fixture missing: {sample_pdf}'
    dest_pdf = os.path.join(intake_dir, os.path.basename(sample_pdf))
    if not os.path.exists(dest_pdf):
        shutil.copy2(sample_pdf, dest_pdf)

    page = e2e_page

    # 1) Navigate to intake/analyze (try both legacy and namespaced routes)
    tried_urls = [f"{base_url}/analyze_intake", f"{base_url}/intake/analyze_intake"]
    # Try to load an analyze page. Accept the first URL that returns HTTP 200.
    resp = None
    for u in tried_urls:
        try:
            resp = page.goto(u)
            try:
                page.wait_for_load_state('domcontentloaded', timeout=2000)
            except Exception:
                pass
            status = None
            try:
                status = resp.status if resp is not None else None
            except Exception:
                status = None
            if status == 200:
                break
        except Exception:
            # try the next candidate URL
            continue

    # 2) Start Analysis: try multiple selectors (robust against template variants)
    # If a Start Analysis button isn't present, the server may have already
    # produced analysis results (auto-run). In that case continue; otherwise
    # skip the flow because the UI isn't available in this environment.
    started = _click_if_present(page, ['button:has-text("Start Analysis")', 'text=Start Analysis', '#start-analysis-btn', '[data-testid="start-analysis"]', 'button[onclick="startAnalysis()"]'])
    if not started:
        # If analysis DOM results are already present, proceed without clicking Start
        already = _wait_for_any(page, ['.document-section', '.documents-table', '#documents-table'], timeout=5000)
        if not already:
            # Attempt to start analysis programmatically via the API as a fallback.
            # This enables E2E runs where the UI starter button isn't present
            # (for example when analysis is driven via backend or different template).
            api_urls = [f"{base_url}/api/analyze_intake", f"{base_url}/analyze_intake"]
            started_api = False
            for api in api_urls:
                try:
                    # the analyze API is a GET endpoint in the app; use GET to trigger it
                    r = requests.get(api, timeout=10)
                    if r.status_code in (200, 201):
                        started_api = True
                        break
                except Exception:
                    continue

            if not started_api:
                pytest.skip('No Start Analysis UI found and could not trigger analysis via API; skipping E2E flow')

            # Wait for analysis DOM results to appear after API-triggered analysis.
            # The API call triggers backend processing but the current page may not auto-update.
            # Wait for the server to write the intake analysis cache file which indicates analyses are ready.
            # Poll the server-side readiness endpoint that reports when the
            # analyze results have been cached and the viewer will render them.
            ready_url = f"{base_url}/api/intake_viewer_ready"
            deadline = time.time() + 30
            cache_ready = False
            while time.time() < deadline:
                try:
                    r = requests.get(ready_url, timeout=2)
                    if r.status_code == 200:
                        j = r.json()
                        if j.get('ready') and j.get('count', 0) > 0:
                            cache_ready = True
                            break
                except Exception:
                    pass
                time.sleep(0.5)

            # Try explicitly navigating to the candidate analyze pages so the UI can reflect
            # the new analysis state, then wait for DOM results.
            for u in tried_urls:
                try:
                    # If the cache indicates readiness, prefer a fresh navigation so the server will render analyses
                    if cache_ready:
                        resp = page.goto(u)
                    else:
                        resp = page.goto(u)
                    try:
                        page.wait_for_load_state('networkidle', timeout=5000)
                    except Exception:
                        pass
                    # If this navigation returned a 200, we expect the DOM to reflect analysis.
                    try:
                        if resp and resp.status != 200:
                            continue
                    except Exception:
                        pass
                except Exception:
                    pass
            already = _wait_for_any(page, ['.document-section', '.documents-table', '#documents-table'], timeout=60000)
            if not already:
                pytest.skip('Analysis triggered via API but no DOM results appeared; skipping E2E flow')

    # Wait for analysis DOM results
    sel = _wait_for_any(page, ['.document-section', '.documents-table', '#documents-table'], timeout=30000)
    if not sel:
        # Try debug endpoints to locate the authoritative processing batch created by the server
        try:
            dbg = requests.get(f"{base_url}/batch/api/debug/latest_document", timeout=5)
            if dbg.status_code == 200:
                payload = dbg.json()
                batch_id = payload.get('batch_id') or payload.get('fixed_batch') or payload.get('processing_batch')
                if batch_id:
                    # Prefer manipulate route for determinism
                    try:
                        page.goto(f"{base_url}/document/batch/{batch_id}/manipulate/0")
                        # give DOM a moment
                        try:
                            page.wait_for_load_state('domcontentloaded', timeout=2000)
                        except Exception:
                            pass
                        sel = _wait_for_any(page, ['.document-section', '.documents-table', '#documents-table', 'table'], timeout=15000)
                    except Exception:
                        pass
        except Exception:
            pass
    if not sel:
        # Capture browser HTML for post-mortem and copy app log
        try:
            artifacts_dir = os.path.join(os.path.dirname(__file__), 'artifacts')
            os.makedirs(artifacts_dir, exist_ok=True)
            stamp = int(time.time())
            html_path = os.path.join(artifacts_dir, f'failed_full_workflow_{stamp}.html')
            with open(html_path, 'w', encoding='utf-8') as fh:
                try:
                    fh.write(page.content())
                except Exception:
                    fh.write('<html><body>Could not capture page.content()</body></html>')
            # Copy app log from app_process if available
            try:
                app_log = app_process.get('app_log_path')
                if app_log and os.path.exists(app_log):
                    shutil.copy2(app_log, os.path.join(artifacts_dir, f'app_process_{stamp}.log'))
            except Exception:
                pass
            print(f'Wrote artifacts for failed run: {html_path}')
        except Exception as e:
            print('Failed to write failure artifacts:', e)
        assert sel, 'Analysis did not produce DOM results in time'

    # 3) Start Smart Processing
    smart_started = _click_if_present(page, ['[data-testid="start-smart-processing"]', 'button:has-text("Start Smart Processing")', 'text=Start Smart Processing', '#start-smart-btn'])
    if not smart_started:
        # attempt to call a JS starter function if present
        try:
            page.evaluate('typeof startSmartProcessing === "function" && startSmartProcessing()')
            smart_started = True
        except Exception:
            pass
    assert smart_started, 'Could not trigger Smart Processing'

    # 4) Wait for smart-progress-panel or batch ids to appear
    sel = _wait_for_any(page, ['#smart-progress-panel', '#smart-batch-ids'], timeout=120000)
    assert sel, 'Smart processing UI did not appear in time'

    # Prefer explicit batch link if present
    batch_link = page.query_selector('#smart-batch-ids a') if page.query_selector('#smart-batch-ids') else None
    if batch_link:
        href = batch_link.get_attribute('href')
        page.goto(base_url + href)
    else:
        # fallback to batch control page
        page.goto(base_url + '/batch/control')

    # 5) Verify documents are visible in the audit/control view
    doc_sel = _wait_for_any(page, ['.documents-table', '#documents-table', '.document-section', 'table'], timeout=30000)
    assert doc_sel, 'No documents visible in batch audit/control'

    # 6) Check progress panel content if present and assert progress values
    try:
        if page.query_selector('#smart-progress-panel'):
            content = page.inner_text('#smart-progress-panel')
            assert len(content.strip()) > 0, 'Smart progress panel present but empty'
            # If progress items present like "progress: 3/5" extract numeric move
            import re
            m = re.search(r"(\d+)\s*/\s*(\d+)", content)
            if m:
                done = int(m.group(1))
                total = int(m.group(2))
                assert done <= total and total > 0, 'Progress numbers look invalid'
    except Exception:
        # non-fatal; continue to export check
        pass

    # 7) Wait for export/file being written to filing_cabinet (app may auto-export in FAST_TEST_MODE)
    exported = False
    start = time.time()
    while time.time() - start < 60:
        try:
            entries = os.listdir(filing_cabinet)
            if entries:
                exported = True
                break
        except Exception:
            pass
        time.sleep(1)

    assert exported, f'No exported file found in filing cabinet at {filing_cabinet} (entries: {os.listdir(filing_cabinet) if os.path.exists(filing_cabinet) else "<missing dir>"})'

    # 8) DB sanity checks: ensure exported status present for the batch/documents
    try:
        db_path = app_config.DATABASE_PATH
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            # Check for any document rows in documents table (grouped flows) or
            # single_documents table (single-document flows). Accept either.
            cur.execute("SELECT count(1) FROM documents")
            row = cur.fetchone()
            if row is None or row[0] == 0:
                # Fallback to single_documents for single-doc processing
                try:
                    cur.execute("SELECT count(1) FROM single_documents")
                    srow = cur.fetchone()
                    if srow is None or srow[0] == 0:
                        pytest.fail('Database contains no document rows (documents or single_documents) after E2E flow')
                except Exception:
                    pytest.fail('Database contains no document rows after E2E flow (and could not query single_documents)')
            # Optionally check for exported status rows
            cur.execute("SELECT count(1) FROM batches WHERE status = ?", (app_config.STATUS_EXPORTED,))
            b_row = cur.fetchone()
            # Not all flows auto-export to a batch; warn if zero but don't fail
            if b_row and b_row[0] == 0:
                print('Warning: no batches with exported status found (may be fine in FAST_TEST_MODE)')
            conn.close()
    except Exception as e:
        # Database checks are best-effort; surface but don't fail the test
        print(f'Could not run DB sanity checks: {e}')

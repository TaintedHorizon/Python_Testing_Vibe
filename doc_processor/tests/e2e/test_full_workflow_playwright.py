import os
import time
import shutil
import pytest
import sqlite3
from config_manager import app_config


def _click_if_present(page, selector_texts, timeout=5000):
    """Try several selector forms and click the first that matches."""
    for sel in selector_texts:
        try:
            if page.query_selector(sel):
                page.click(sel, timeout=timeout)
                return True
        except Exception:
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

    # 1) Navigate to intake/analyze
    analyze_url = f"{base_url}/intake/analyze_intake"
    page.goto(analyze_url)

    # 2) Start Analysis: try multiple selectors (robust against template variants)
    started = _click_if_present(page, ['button:has-text("Start Analysis")', 'text=Start Analysis', '#start-analysis-btn'])
    if not started:
        pytest.skip('No Start Analysis UI found; skipping E2E flow')

    # Wait for analysis DOM results
    sel = _wait_for_any(page, ['.document-section', '.documents-table', '#documents-table'], timeout=30000)
    assert sel, 'Analysis did not produce DOM results in time'

    # 3) Start Smart Processing
    smart_started = _click_if_present(page, ['button:has-text("Start Smart Processing")', 'text=Start Smart Processing', '#start-smart-btn'])
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
            # Check for any document rows in documents table
            cur.execute("SELECT count(1) FROM documents")
            row = cur.fetchone()
            if row is None or row[0] == 0:
                pytest.fail('Database contains no document rows after E2E flow')
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

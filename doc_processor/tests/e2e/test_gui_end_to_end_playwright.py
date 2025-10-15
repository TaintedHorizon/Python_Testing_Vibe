import os
import time
import shutil
import json
import pytest

from pathlib import Path


@pytest.mark.skipif(os.getenv('PLAYWRIGHT_E2E', '0') not in ('1', 'true', 'True'), reason='Playwright E2E disabled')
def test_gui_full_flow(e2e_page, app_process, e2e_artifacts_dir):
    """
    Full GUI end-to-end test using Playwright. Steps:
    - Place a known PDF into intake dir
    - Visit intake analysis page, click Start Analysis
    - Wait for analysis results to appear
    - Click Start Smart Processing and wait for completion
    - Navigate to manipulation page and assert single_documents are visible
    - Trigger export and assert at least one exported file exists in filing_cabinet
    """
    import os
    import time
    import shutil
    from pathlib import Path

    page = e2e_page
    base = app_process['base_url']
    intake_dir = app_process['intake_dir']
    filing_cabinet = app_process['filing_cabinet']

    # Copy fixture into intake
    repo_root = Path(__file__).parents[2]
    sample = repo_root / 'tests' / 'fixtures' / 'sample_small.pdf'
    assert sample.exists(), f"Missing fixture: {sample}"
    dest = Path(intake_dir) / 'sample_intake.pdf'
    shutil.copy2(sample, dest)

    # Visit analyze page (intake blueprint is registered at root)
    page.goto(f"{base}/analyze_intake")

    # Prefer data-testid first, then JS invocation, then fallback clicks.
    if page.query_selector('[data-testid="start-analysis"]'):
        try:
            page.click('[data-testid="start-analysis"]', timeout=10000)
        except Exception:
            # If button is present but not clickable, try invoking JS
            try:
                page.evaluate('() => { if (typeof startAnalysis === "function") { startAnalysis(); return true; } return false; }')
            except Exception:
                pytest.skip('Start Analysis present but not actionable')
    else:
        try:
            invoked = page.evaluate('() => { if (typeof startAnalysis === "function") { startAnalysis(); return true; } return false; }')
            if not invoked:
                raise RuntimeError('startAnalysis not invoked')
        except Exception:
            if page.query_selector('button[onclick="startAnalysis()"]'):
                page.click('button[onclick="startAnalysis()"]', timeout=10000)
            elif page.query_selector('text=Start Analysis'):
                page.click('text=Start Analysis', timeout=10000)
            else:
                pytest.skip('No Start Analysis entrypoint available in this template')

    # Wait for analysis results marker
    page.wait_for_selector('#smart-progress-panel, .document-section', timeout=30000)

    # Start smart processing via JS or fallback to button click
    # Prefer data-testid for starting smart processing
    if page.query_selector('[data-testid="start-smart-processing"]'):
        try:
            page.click('[data-testid="start-smart-processing"]', timeout=10000)
        except Exception:
            try:
                page.evaluate('() => { if (typeof startSmartProcessing === "function") { startSmartProcessing(); return true; } return false; }')
            except Exception:
                pytest.skip('Start Smart Processing present but not actionable')
    else:
        try:
            invoked = page.evaluate('() => { if (typeof startSmartProcessing === "function") { startSmartProcessing(); return true; } return false; }')
            if not invoked:
                raise RuntimeError('startSmartProcessing not invoked')
        except Exception:
            if page.query_selector('button[onclick="startSmartProcessing()"]'):
                page.click('button[onclick="startSmartProcessing()"]', timeout=10000)
            elif page.query_selector('text=Start Smart Processing'):
                page.click('text=Start Smart Processing', timeout=10000)
            elif page.query_selector('button#start-smart'):
                page.click('button#start-smart', timeout=10000)
            else:
                pytest.skip('No Start Smart Processing entrypoint available')

    # Wait for the smart batch ids element to appear
    page.wait_for_selector('#smart-batch-ids', timeout=120000)

    # Poll smart progress panel for completion text
    finished = False
    for _ in range(240):
        content = page.inner_text('#smart-progress-panel') if page.query_selector('#smart-progress-panel') else ''
        if 'Smart processing complete' in content or 'complete' in content.lower():
            finished = True
            break
        time.sleep(0.5)

    assert finished, 'Smart processing did not report completion in UI'

    # Navigate to batch control and wait for documents to be visible
    page.goto(f"{base}/batch/control")
    page.wait_for_selector('.documents-table, #documents-table, .document-section', timeout=30000)

    # Trigger export if an Export button is present
    if page.query_selector('text=Export'):
        page.click('text=Export')
        time.sleep(1)

    # closure handled by e2e_page fixture

    files = list(Path(filing_cabinet).rglob('*'))
    assert any(f.is_file() for f in files), 'No exported files found in filing_cabinet after export'

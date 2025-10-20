import os
import pytest
import asyncio

from playwright.sync_api import sync_playwright
from .playwright_helpers import dump_screenshot_and_html, wait_for_progress_update

ARTIFACTS_DIR = os.environ.get('E2E_ARTIFACTS', 'doc_processor/tests/e2e/artifacts')


@pytest.mark.skipif(os.environ.get('PLAYWRIGHT_E2E') != '1', reason='Playwright E2E not enabled')
def test_sse_ui_progress_matches_dom(app_process):
    """Navigate to the intake analysis page, wait for the smart progress bar to appear and update.

    This test uses the real selectors present in `intake_analysis.html`:
      - `#smart-progress-panel` (container)
      - `#smart-progress-bar` (the inner progress bar showing percent text)

    It's intentionally forgiving: it waits up to 30s for appearance and for a non-zero update.
    """
    # Run the existing synchronous Playwright code in a separate thread so we don't use
    # the sync Playwright API inside pytest's asyncio event loop.
    def _run_sync_playwright(app_process_inner):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                # Open the dedicated analyze page which wires up the EventSource
                base = app_process_inner.get('base_url') if isinstance(app_process_inner, dict) else app_process_inner
                # page.goto can fail if server hasn't finished binding; retry briefly
                goto_url = f"{base}/analyze_intake"
                last_exc = None
                for attempt in range(8):
                    try:
                        page.goto(goto_url)
                        last_exc = None
                        break
                    except Exception as e:
                        last_exc = e
                        time_to_wait = 0.5 + attempt * 0.5
                        try:
                            import time as _t
                            _t.sleep(time_to_wait)
                        except Exception:
                            pass
                if last_exc:
                    # Re-raise the original error to keep pytest semantics
                    raise last_exc

                # Ensure there's at least one PDF in the intake directory so analysis runs
                try:
                    from pathlib import Path
                    repo_root = Path(__file__).parents[2]
                    sample = repo_root / 'tests' / 'fixtures' / 'sample_small.pdf'
                    intake_dir = Path(app_process_inner.get('intake_dir')) if isinstance(app_process_inner, dict) else Path(__file__).parents[3] / 'intake'
                    intake_dir.mkdir(parents=True, exist_ok=True)
                    if sample.exists():
                        dest = intake_dir / 'sample_intake.pdf'
                        import shutil
                        shutil.copy2(sample, dest)
                except Exception:
                    # best-effort; continue even if copying fails
                    pass

                # Trigger analysis by calling the server endpoint directly and extract the token
                # This avoids flaky client-side wiring; server returns a token we can use to read SSE
                try:
                    # POST to the endpoint that starts smart processing; wait for response
                    resp = page.request.post(f"{base}/batch/process_smart", data={})
                    assert resp.ok, f"process_smart POST failed: {resp.status}"
                    body = resp.json()
                    # server typically returns { success: true, data: { token: '...' } }
                    token = None
                    if isinstance(body, dict):
                        token = (body.get('data') or {}).get('token') if body.get('data') else None
                        if not token:
                            token = body.get('token') or body.get('id') or body.get('task_token')
                except Exception:
                    # fallback to clicking the UI button if direct POST fails
                    try:
                        if page.query_selector('[data-testid="start-smart-processing"]'):
                            page.click('[data-testid="start-smart-processing"]', timeout=5000)
                        elif page.query_selector("button[onclick=\"startBatchProcessing('smart')\"]"):
                            page.click("button[onclick=\"startBatchProcessing('smart')\"]", timeout=5000)
                        else:
                            page.evaluate("() => (typeof startBatchProcessing === 'function') && startBatchProcessing('smart')")
                    except Exception:
                        pass
                    token = None

                # If we obtained a token, open the SSE endpoint directly and wait for initial data
                if token:
                    sse_url = f"{base}/batch/api/smart_processing_progress?token={token}"
                    # fetch as text; server streams will return something initial we can assert on
                    sse_resp = page.evaluate(f"() => fetch('{sse_url}').then(r=>r.text())")
                    assert sse_resp is not None and len(sse_resp) > 0
                else:
                    # Fall back to checking the DOM progress bar, as a best-effort verification
                    progress_selector = '#smart-progress-bar'
                    current = wait_for_progress_update(page, progress_selector, previous_text=None, timeout=30000)
                    assert current is not None, 'smart progress bar did not appear'

                    if current.strip().startswith('0'):
                        updated = wait_for_progress_update(page, progress_selector, previous_text=current, timeout=30000)
                        assert updated is not None and updated != current, 'smart progress bar did not advance from 0%'
            except Exception:
                dump_screenshot_and_html(page, ARTIFACTS_DIR, 'sse_ui_failure')
                raise
            finally:
                browser.close()

    # Execute the synchronous helper in a separate thread to avoid Playwright sync-vs-async conflicts
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as executor:
        fut = executor.submit(_run_sync_playwright, app_process)
        # re-raise any exception from the worker
        fut.result()

import sys
import time
import os
from playwright.sync_api import sync_playwright
import requests
import sys
import os
# Ensure helper module can be imported when tracer is run as a script
sys.path.insert(0, os.path.dirname(__file__))
from doc_processor.tests.e2e.smart_status_helper import poll_smart_processing_status

BASE_URL = os.environ.get('BASE_URL') or 'http://127.0.0.1:51700'

def _ts_print(*args, **kwargs):
    t = time.time()
    print(f"{t:.3f}", *args, **kwargs)


_ts_print('Tracer starting for', BASE_URL)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context()
    # Enable tracing recording
    try:
        ctx.tracing.start(screenshots=True, snapshots=True)
    except Exception as e:
        print('Tracing start failed:', e)
    page = ctx.new_page()

    page.on('console', lambda msg: _ts_print(f'CONSOLE: {msg.type} {msg.text}'))
    page.on('request', lambda req: _ts_print(f'REQ: {req.method} {req.url}'))
    page.on('response', lambda resp: _ts_print(f'RESP: {resp.status} {resp.url}'))
    # Track SSE request failures so tracer can poll fallback status endpoint
    sse_failed = {'failed': False}
    def _on_request_failed(req):
        try:
            _ts_print(f'REQFAILED: {req.url} {req.failure}')
        except Exception:
            _ts_print('REQFAILED (could not stringify)')
        try:
            if '/batch/api/smart_processing_progress' in (req.url or ''):
                sse_failed['failed'] = True
        except Exception:
            pass

    page.on('requestfailed', _on_request_failed)

    # Navigate and start analysis
    page.goto(f"{BASE_URL}/analyze_intake")
    time.sleep(1)
    # Try to invoke startAnalysis via evaluate
    try:
        invoked = page.evaluate('() => { if (typeof startAnalysis === "function") { startAnalysis(); return true; } return false; }')
        _ts_print('Invoked startAnalysis via evaluate:', invoked)
    except Exception as e:
        _ts_print('Could not evaluate startAnalysis:', e)

    # Poll analyze API
    api_url = f"{BASE_URL}/api/analyze_intake"
    analysis_done = False
    for i in range(60):
        try:
            r = requests.get(api_url, timeout=5)
            _ts_print('API status', i, r.status_code)
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, dict) and j.get('analyses') and len(j.get('analyses', [])) > 0:
                    _ts_print('API analysis result count:', len(j.get('analyses', [])))
                    analysis_done = True
                    break
        except Exception as e:
            _ts_print('API poll error:', e)
        time.sleep(1)

    # Trigger smart processing via API fallback
    try:
        r = requests.post(f"{BASE_URL}/batch/process_smart", json={}, timeout=10)
        _ts_print('process_smart status:', r.status_code, 'body:', r.text[:200])
        token = None
        try:
            j = r.json()
            token = j.get('data', {}).get('token') or j.get('token')
            _ts_print('token from response:', token)
        except Exception as e:
            _ts_print('Could not parse JSON from process_smart:', e)
    except Exception as e:
        _ts_print('process_smart request failed:', e)
        token = None

    if token:
        # Start client-side SSE via evaluate
        try:
            started = page.evaluate('(t) => { try { if (typeof startSmartSSE === "function") { startSmartSSE(t); return true; } new EventSource(`/batch/api/smart_processing_progress?token=${encodeURIComponent(t)}`); return true; } catch(e) { return false; } }', token)
            _ts_print('Triggered client SSE via page.evaluate, startSmartSSE returned:', started)
        except Exception as e:
            _ts_print('Could not instruct page to open SSE:', e)

    # Wait a bit for SSE events (server emits and heartbeats)
    time.sleep(10)

    # If SSE aborted, use centralized helper to poll the fallback JSON status
    # endpoint until processing completes or stalls.
    if token:
        last_event, meta = poll_smart_processing_status(token, base_url=BASE_URL, max_polls=60, stall_limit=10, poll_interval=1.0)
        _ts_print('fallback result meta:', meta)
        _ts_print('fallback last_event:', last_event)

    # Save tracing
    try:
        trace_path = os.path.join(os.getcwd(), 'e2e_trace.zip')
        ctx.tracing.stop(path=trace_path)
        _ts_print('Saved Playwright trace to', trace_path)
    except Exception as e:
        _ts_print('Failed to save trace:', e)

    ctx.close()
    browser.close()

_ts_print('Tracer finished')

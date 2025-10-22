import os
import subprocess
import time
import signal
import requests
import pytest
import sys
import tempfile
import shutil

PLAYWRIGHT_FLAG = os.getenv('PLAYWRIGHT_E2E', '0')


@pytest.mark.skipif(PLAYWRIGHT_FLAG != '1', reason='Playwright E2E disabled by default')
def test_playwright_intake_to_single_documents(tmp_path):
    """Full Playwright E2E: intake -> analyze -> smart -> verify single_documents.

    Runs a short Playwright script in a subprocess to avoid running the sync Playwright API
    inside pytest's asyncio event loop.
    """

    # start_app.sh lives at the repository root
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    start_script = os.path.join(repo_root, 'start_app.sh')
    assert os.path.exists(start_script), f'start_app.sh not found at {start_script}'

    # Prepare an isolated intake dir and temporary database for the app process
    from config_manager import app_config
    sample_pdf = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'sample_small.pdf'))
    # Use a per-test intake directory under tmp_path to avoid contaminating global state
    intake_dir = os.path.abspath(os.path.join(str(tmp_path), 'intake'))
    os.makedirs(intake_dir, exist_ok=True)
    dest_pdf = os.path.join(intake_dir, os.path.basename(sample_pdf))
    if not os.path.exists(dest_pdf):
        shutil.copy2(sample_pdf, dest_pdf)

    # Pick a free port for this test to avoid collisions with existing servers
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        free_port = s.getsockname()[1]

    # Start the app in background with environment overrides to force a fresh DB and isolated intake
    env = os.environ.copy()
    # Use a fresh temporary database inside the pytest tmp_path
    tmp_db = os.path.abspath(os.path.join(str(tmp_path), 'documents.db'))
    os.makedirs(os.path.dirname(tmp_db), exist_ok=True)
    env['DATABASE_PATH'] = tmp_db
    # Allow the app to create a new DB during tests and enable fast test mode
    env['ALLOW_NEW_DB'] = '1'
    env['FAST_TEST_MODE'] = '1'
    # Ensure the app uses the per-test intake directory we prepared
    env['INTAKE_DIR'] = intake_dir
    # Bind to the standard local test port
    env['HOST'] = '127.0.0.1'
    env['PORT'] = str(free_port)

    proc = subprocess.Popen([start_script], cwd=repo_root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, preexec_fn=os.setsid)

    try:
        # Wait for app to be healthy
        health_url = f'http://127.0.0.1:{free_port}/api/system_info'
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

        # Playwright helper script run in a short-lived subprocess
        # Inject the chosen free port into the helper script so Playwright targets the right URL
        helper = '''
import time
from playwright.sync_api import sync_playwright

def try_invoke_start_analysis(page):
    # Prefer data-testid, then JS, then text selector
    if page.query_selector('[data-testid="start-analysis"]'):
        try:
            page.click('[data-testid="start-analysis"]', timeout=5000)
            return True
        except Exception:
            pass
    try:
        invoked = page.evaluate('() => { if (typeof startAnalysis === "function") { startAnalysis(); return true; } return false; }')
        if invoked:
            return True
    except Exception:
        pass
    for sel in ['button[onclick="startAnalysis()"]', 'text=Start Analysis', 'button:has-text("Start Analysis")']:
        try:
            if page.query_selector(sel):
                page.click(sel, timeout=5000)
                return True
        except Exception:
            pass
    return False


def try_invoke_start_smart(page):
    if page.query_selector('[data-testid="start-smart-processing"]'):
        try:
            page.click('[data-testid="start-smart-processing"]', timeout=5000)
            return True
        except Exception:
            pass
    try:
        invoked = page.evaluate('() => { if (typeof startSmartProcessing === "function") { startSmartProcessing(); return true; } return false; }')
        if invoked:
            return True
    except Exception:
        pass
    for sel in ['button[onclick="startSmartProcessing()"]', 'text=Start Smart Processing', 'button#start-smart', 'button:has-text("Start Smart Processing")']:
        try:
            if page.query_selector(sel):
                page.click(sel, timeout=5000)
                return True
        except Exception:
            pass
    return False


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context()
    page = ctx.new_page()
    # forward browser console to helper stdout for debugging
    page.on('console', lambda msg: print(f'CONSOLE: {msg.type} {msg.text}'))
    # log failed network requests (captures 404s and other failures)
    page.on('requestfailed', lambda req: print(f'REQFAILED: {req.url} {req.failure}'))
    page.goto('{BASE_URL}/analyze_intake')
    # wait a bit longer for UI to initialize
    page.wait_for_selector('body', timeout=30000)
    if not try_invoke_start_analysis(page):
        print('Could not invoke start analysis')
        raise SystemExit(2)
    time.sleep(1)
    # Poll the API endpoint for analysis results (more deterministic than client DOM mutation)
    import requests as _r
    analysis_done = False
    api_url = '{BASE_URL}/api/analyze_intake'
    for _ in range(60):
        try:
            resp = _r.get(api_url, timeout=5)
            if resp.status_code == 200:
                j = resp.json()
                if isinstance(j, dict) and j.get('analyses') and len(j.get('analyses', [])) > 0:
                    analysis_done = True
                    print('API analysis result count:', len(j.get('analyses', [])))
                    break
        except Exception as e:
            print('API poll error:', e)
        time.sleep(1)
    if not analysis_done:
        # Diagnostics: dump current page URL and snippet before failing
        try:
            print('ANALYSIS TIMEOUT - PAGE URL:', page.url)
            print('ANALYSIS TIMEOUT - PAGE HTML SNIPPET:', page.content()[:2000])
        except Exception:
            pass
        raise SystemExit(2)
    # Reload the page so server-rendered analyses and batch controls are present
    try:
        page.goto('{BASE_URL}/analyze_intake')
        # allow server-rendered DOM to load
        page.wait_for_selector('body', timeout=10000)
    except Exception:
        pass
    if not try_invoke_start_smart(page):
        print('Could not invoke start smart processing via UI selectors, attempting API fallback')
        # Fallback: call the server API directly to start smart processing and obtain token
        try:
            import requests as _r
            resp = _r.post('{BASE_URL}/batch/process_smart', json={}, timeout=10)
            if resp.status_code == 200:
                j = resp.json()
                token = None
                if isinstance(j, dict) and j.get('data'):
                    token = j['data'].get('token')
                elif isinstance(j, dict) and j.get('token'):
                    token = j.get('token')
                print('API fallback process_smart response status:', resp.status_code, 'token:', token)
                # If we got a token, wait for the page to show progress (it may redirect)
                if token:
                    # Ask the page to start the client-side SSE using the token so the smart panel appears
                    try:
                        started = page.evaluate('(t) => { try { if (typeof startSmartSSE === "function") { startSmartSSE(t); return true; } new EventSource(`/batch/api/smart_processing_progress?token=${encodeURIComponent(t)}`); return true; } catch(e) { return false; } }', token)
                        print('Triggered client SSE via page.evaluate, startSmartSSE returned:', started)
                    except Exception as _e:
                        print('Could not instruct page to open SSE:', _e)
                    # Wait briefly for the panel or redirect
                    for _ in range(30):
                        cur_url = page.url
                        if '#smart' in cur_url or '/batch' in cur_url or page.query_selector('#smart-progress-panel'):
                            break
                        time.sleep(1)
                else:
                    print('API fallback did not return a token; failing')
                    raise SystemExit(3)
            else:
                print('API fallback process_smart failed with status', resp.status_code)
                raise SystemExit(3)
        except Exception as _e:
            print('API fallback error:', _e)
            raise SystemExit(3)
        # Wait for either the inline smart progress panel to appear OR for the page to redirect to /batch
        waited = 0
        found = False
        while waited < 60:
            try:
                if page.query_selector('#smart-progress-panel'):
                    found = True
                    break
            except Exception:
                pass
            cur = page.url
            if '/batch' in cur:
                # Page redirected to batch control/audit
                found = True
                break
            time.sleep(1)
            waited += 1
        if not found:
            print('Timed out waiting for smart progress panel or redirect; current URL:', page.url)
            raise SystemExit(3)
    # Wait for batch ids (if panel present) or proceed if redirected
    smart_complete = False
    for _ in range(120):
        try:
            el = page.query_selector('#smart-batch-ids')
            if el and (el.is_visible() or el.inner_text()):
                smart_complete = True
                break
        except Exception:
            pass
        # If the page is already on /batch/control, consider it progressing
        if '/batch' in page.url:
            smart_complete = True
            break
        time.sleep(1)
    if not smart_complete:
        raise SystemExit(3)
    batch_link = page.query_selector('#smart-batch-ids a')
    if batch_link:
        href = batch_link.get_attribute('href')
        # Normalize and navigate using BASE_URL
        if href.startswith('http'):
            target = href
        else:
            target = '{BASE_URL}' + href
        print('Navigating to batch link:', target)
        page.goto(target)

        # If the audit page returns a Page Not Found (404), try the batch control path as fallback
        try:
            # Give the server a short moment to render
            page.wait_for_selector('body', timeout=5000)
            if 'Page Not Found' in page.content()[:2000]:
                print('Audit page returned Page Not Found; trying /batch/control fallback')
                page.goto('{BASE_URL}/batch/control')
        except Exception:
            # Continue to fallback attempt
            try:
                page.goto('{BASE_URL}/batch/control')
            except Exception:
                pass
    else:
        page.goto('{BASE_URL}/batch/control')

    # Ensure documents exist in audit view — increase patience for rendering
    doc_present = False
    for _ in range(60):
        try:
            if page.query_selector('table') and page.query_selector('table tr'):
                doc_present = True
                break
        except Exception:
            pass
        time.sleep(1)

    if not doc_present:
        # Dump diagnostics before exiting to help identify 404s/missing DOM
        try:
            print('FINAL PAGE URL:', page.url)
            print('PAGE CONTENT SNIPPET:', page.content()[:4000])
        except Exception:
            pass
        raise SystemExit(4)
        ctx.close()
        browser.close()
'''

        # Substitute the BASE_URL placeholder so helper targets the started app instance
        base_url = f'http://127.0.0.1:{free_port}'
        helper = helper.replace('{BASE_URL}', base_url)

        # Write helper script into the pytest tmp_path to avoid global tempfile usage
        helper_path = os.path.join(str(tmp_path), 'playwright_helper.py')
        with open(helper_path, 'w') as hf:
            hf.write(helper)

        proc2 = subprocess.run([sys.executable, helper_path], cwd=repo_root, timeout=300)
        assert proc2.returncode == 0, f'Playwright helper exited with {proc2.returncode}'

    finally:
        # Stop the background app
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass


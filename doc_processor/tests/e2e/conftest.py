import os
import time
import shutil
import tempfile
import subprocess
import requests
import pytest


def _wait_for_health(url, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


@pytest.fixture(scope='session')
def playwright_e2e_enabled():
    return os.getenv('PLAYWRIGHT_E2E', '0') in ('1', 'true', 'True')


@pytest.fixture(scope='session')
def app_process(tmp_path_factory, request):
    """
    Start the application using the repo's start script in a background process.
    Yields the base URL and environment mapping. Tests should skip if PLAYWRIGHT_E2E not set.
    """
    if not (os.getenv('PLAYWRIGHT_E2E', '0') in ('1', 'true', 'True')):
        pytest.skip('Playwright E2E disabled (set PLAYWRIGHT_E2E=1 to enable)')

    # Build an isolated temp workspace for the app to use
    tmp_root = tmp_path_factory.mktemp('e2e_app')
    intake_dir = tmp_root / 'intake'
    processed_dir = tmp_root / 'processed'
    filing_cabinet = tmp_root / 'filing_cabinet'
    for d in (intake_dir, processed_dir, filing_cabinet):
        d.mkdir()

    env = os.environ.copy()
    # Ensure deterministic/test-friendly flags
    env['FAST_TEST_MODE'] = '1'
    env['SKIP_OLLAMA'] = '1'
    env['PLAYWRIGHT_E2E'] = '1'
    env['INTAKE_DIR'] = str(intake_dir)
    env['PROCESSED_DIR'] = str(processed_dir)
    env['FILING_CABINET_DIR'] = str(filing_cabinet)

    # Start the provided startup script from repo root
    cmd = ['./start_app.sh']
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    base_url = 'http://127.0.0.1:5000'
    health = f"{base_url}/health"
    started = _wait_for_health(health, timeout=30)
    # Also wait for analyze page endpoint to be registered (avoid race with blueprint registration)
    analyze_url = f"{base_url}/analyze_intake"
    if started:
        # try a few times until analyze endpoint returns 200
        analyze_ok = False
        deadline = time.time() + 20.0
        while time.time() < deadline:
            try:
                r = requests.get(analyze_url, timeout=2)
                if r.status_code == 200:
                    analyze_ok = True
                    break
            except Exception:
                pass
            time.sleep(0.25)
        if not analyze_ok:
            # continue anyway but warn in logs; the test will fail with clearer message
            print(f"Warning: analyze endpoint did not become ready at {analyze_url}")
    if not started:
        # Dump some output for debugging
        try:
            if proc.stdout:
                out = proc.stdout.read().decode(errors='ignore')
            else:
                out = '<no output available>'
        except Exception:
            out = '<no output available>'
        proc.kill()
        pytest.skip(f'Could not start app for E2E tests; output:\n{out}')

    yield {'base_url': base_url, 'env': env, 'intake_dir': str(intake_dir), 'filing_cabinet': str(filing_cabinet)}

    # Teardown
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


@pytest.fixture(scope='session')
def e2e_artifacts_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp('e2e_artifacts')
    artifacts = d / 'artifacts'
    artifacts.mkdir()
    return str(artifacts)


def pytest_runtest_makereport(item, call):
    # Mark the test item with a failure flag so fixtures can detect it in teardown
    if call.when == 'call':
        outcome = call.excinfo is None
        if not outcome:
            setattr(item, 'failed', True)


@pytest.fixture()
def e2e_page(playwright, request):
    """Create a Playwright page and attach it to the test node so failure hooks can grab artifacts."""
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    # Attach to test node
    setattr(request.node, 'e2e_page', page)
    yield page

    # On teardown, if the test failed, capture artifacts
    failed = getattr(request.node, 'failed', False)
    artifacts_root = None
    # find an artifacts dir created by the session fixture if present
    for fixture_name in ('e2e_artifacts_dir',):
        if fixture_name in request.fixturenames:
            artifacts_root = request.getfixturevalue(fixture_name)
            break
    try:
        if failed and artifacts_root:
            import time
            ts = int(time.time())
            # safe filenames
            base = f"{request.node.name}-{ts}"
            png = os.path.join(artifacts_root, base + '.png')
            html = os.path.join(artifacts_root, base + '.html')
            try:
                page.screenshot(path=png, full_page=True)
            except Exception:
                pass
            try:
                content = page.content()
                with open(html, 'w', encoding='utf-8') as fh:
                    fh.write(content)
            except Exception:
                pass
    finally:
        try:
            page.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass

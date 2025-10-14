import os
import time
import shutil
import tempfile
import subprocess
import requests
import pytest
from pathlib import Path


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
def app_process(tmp_path_factory, request, e2e_artifacts_dir):
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
    # Route application stdout/stderr to a rotating log file in the artifacts directory
    log_path = os.path.join(e2e_artifacts_dir, 'app_process.log')
    log_fh = open(log_path, 'ab')
    proc = subprocess.Popen(cmd, env=env, stdout=log_fh, stderr=subprocess.STDOUT)

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

    yield {
        'base_url': base_url,
        'env': env,
        'intake_dir': str(intake_dir),
        'filing_cabinet': str(filing_cabinet),
        'proc': proc,
        'app_log_path': log_path,
    }

    # Teardown
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    try:
        log_fh.close()
    except Exception:
        pass


@pytest.fixture(scope='session')
def e2e_artifacts_dir(tmp_path_factory):
    # Allow overriding via env var for CI
    env_dir = os.getenv('E2E_ARTIFACTS_DIR')
    if env_dir:
        os.makedirs(env_dir, exist_ok=True)
        return env_dir

    # Default to a repo-local deterministic artifacts directory
    repo_root = Path(__file__).resolve().parents[4]
    artifacts = repo_root / 'doc_processor' / 'tests' / 'e2e' / 'artifacts'
    artifacts.mkdir(parents=True, exist_ok=True)
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

    # On teardown, if the test failed, capture artifacts and server logs
    failed = getattr(request.node, 'failed', False)
    artifacts_root = None
    # find an artifacts dir created by the session fixture if present
    if 'e2e_artifacts_dir' in request.fixturenames:
        artifacts_root = request.getfixturevalue('e2e_artifacts_dir')
        if failed and artifacts_root:
            import time as _time
            ts = int(_time.time())
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

            # Attempt to capture the application log if available via the app_process fixture
            try:
                if 'app_process' in request.fixturenames:
                    app_proc = request.getfixturevalue('app_process')
                    app_log = app_proc.get('app_log_path')
                    if app_log and os.path.exists(app_log):
                        # copy to artifacts with timestamped name
                        dest_log = os.path.join(artifacts_root, base + '-app.log')
                        try:
                            import shutil as _sh
                            _sh.copyfile(app_log, dest_log)
                        except Exception:
                            pass
            except Exception:
                pass

    # Always attempt to close Playwright objects
    try:
        page.close()
    except Exception:
        pass
    try:
        browser.close()
    except Exception:
        pass

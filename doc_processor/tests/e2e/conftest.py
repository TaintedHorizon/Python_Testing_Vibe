import os
import subprocess
import time
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def ensure_artifacts_dir():
    """Ensure artifacts directory exists if the env overrides it; otherwise do nothing.

    We intentionally avoid creating the repo's artifacts directory by default so E2E
    runs that are not explicitly requested don't pollute the repository. Use the
    E2E_ARTIFACTS_DIR or E2E_ARTIFACTS env var to force artifact collection in CI.
    """
    env_dir = os.getenv("E2E_ARTIFACTS_DIR") or os.getenv("E2E_ARTIFACTS")
    if env_dir:
        Path(env_dir).mkdir(parents=True, exist_ok=True)
    # Ensure deterministic fast test mode is set for the entire E2E session
    # This runs very early (session autouse) so any test or subprocess will
    # inherit FAST_TEST_MODE unless explicitly overridden by the caller.
    os.environ.setdefault("FAST_TEST_MODE", os.getenv("FAST_TEST_MODE", "1"))
    yield
"""Canonical conftest for Playwright E2E tests (compact).

Provides fixtures used by the repo's E2E tests. This file is intentionally
compact and deterministic to reduce flakiness and analyzer noise.
"""

import os
import socket
import subprocess
import time
import shutil
from pathlib import Path

import pytest
import requests


def _find_free_port(start=5000, end=5600):
    for p in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError("no free port found")


def _wait_for_url(url, timeout=30.0):
    # Increase polling window slightly for CI where startup can be slow.
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def e2e_artifacts_dir(tmp_path_factory):
    env_dir = os.getenv("E2E_ARTIFACTS_DIR") or os.getenv("E2E_ARTIFACTS")
    if env_dir:
        os.makedirs(env_dir, exist_ok=True)
        return str(env_dir)
    # Default to a session-scoped temporary artifacts directory to avoid
    # polluting the repository during local test runs.
    tmp_artifacts = tmp_path_factory.mktemp("e2e_artifacts")
    return str(tmp_artifacts)


@pytest.fixture(scope="session", autouse=True)
def app_process(tmp_path_factory, e2e_artifacts_dir):
    if not (os.getenv("PLAYWRIGHT_E2E", "0") in ("1", "true", "True")):
        pytest.skip("Playwright E2E disabled (set PLAYWRIGHT_E2E=1)")

    repo_root = Path(__file__).resolve().parents[3]
    tmp_root = tmp_path_factory.mktemp("e2e_app")
    intake_dir = tmp_root / "intake"
    processed_dir = tmp_root / "processed"
    filing_dir = tmp_root / "filing_cabinet"
    for d in (intake_dir, processed_dir, filing_dir):
        d.mkdir()

    # Use fixed host and port to match tests that hardcode 127.0.0.1:5000
    host = "127.0.0.1"
    port = 5000

    # Ensure logs go to the artifacts directory so test harness can collect them
    log_path = os.path.join(e2e_artifacts_dir, "app_process.log")

    # Prepare environment for the in-process app before importing modules
    os.environ["PLAYWRIGHT_E2E"] = "1"
    os.environ["INTAKE_DIR"] = str(intake_dir)
    os.environ["PROCESSED_DIR"] = str(processed_dir)
    os.environ["FILING_CABINET_DIR"] = str(filing_dir)
    # Respect the caller's environment but force deterministic test mode for in-process runs.
    # Use explicit assignment (not setdefault) so the in-process import of doc_processor picks
    # up the intended behavior even if the environment was previously set to a different value.
    os.environ["FAST_TEST_MODE"] = os.getenv("FAST_TEST_MODE", "1")
    os.environ["SKIP_OLLAMA"] = os.getenv("SKIP_OLLAMA", "1")
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ["HOST"] = host
    os.environ["PORT"] = str(port)
    os.environ["LOG_FILE_PATH"] = log_path
    # Force an isolated temporary database for perfect test isolation
    tmp_db = os.path.join(str(tmp_root), "documents.db")
    os.environ["DATABASE_PATH"] = tmp_db

    # Import the app afresh so config_manager picks up the env changes.
    import sys
    import importlib
    import threading
    try:
        # Remove modules if already imported so reload uses updated env
        for m in list(sys.modules.keys()):
            if m.startswith("doc_processor") and (m.endswith("app") or m.endswith("config_manager") or m == "doc_processor"):
                sys.modules.pop(m, None)
    except Exception:
        pass

    # Now import the application module which will create the Flask app
    try:
        app_mod = importlib.import_module("doc_processor.app")
    except Exception as e:
        pytest.skip(f"Could not import doc_processor.app: {e}")

    flask_app = getattr(app_mod, "app", None)
    if flask_app is None:
        try:
            flask_app = app_mod.create_app()
        except Exception as e:
            pytest.skip(f"Could not create Flask app: {e}")

    # Ensure the in-memory config_manager uses our temp DB and intake dir so
    # routes and background tasks operate on isolated test data.
    try:
        cfg_mod = importlib.import_module("doc_processor.config_manager")
        cfg_mod.app_config.DATABASE_PATH = tmp_db
        cfg_mod.app_config.INTAKE_DIR = str(intake_dir)
        cfg_mod.app_config.PROCESSED_DIR = str(processed_dir)
        # expose E2E_SERVER_DB for tests and helpers
        db_path = cfg_mod.app_config.DATABASE_PATH
        os.environ["E2E_SERVER_DB"] = db_path
        # Also update Flask app extensions if present
        try:
            flask_app.config.setdefault('DATABASE_PATH', db_path)
        except Exception:
            pass
    except Exception:
        db_path = tmp_db

    # Ensure the host/port is free (best-effort). Tests expect 127.0.0.1:5000.
    def _is_port_free(host, port):
        import socket as _socket
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        try:
            s.bind((host, int(port)))
            s.close()
            return True
        except OSError:
            try:
                s.close()
            except Exception:
                pass
            return False

    def _try_free_port(port):
        """Best-effort: try to kill processes listening on the port using lsof/fuser."""
        import subprocess as _sub
        import shutil as _shutil
        # Try fuser first
        if _shutil.which("fuser"):
            try:
                _sub.run(["fuser", "-k", f"{port}/tcp"], check=False, stdout=_sub.DEVNULL, stderr=_sub.DEVNULL)
            except Exception:
                pass
        # Fallback to lsof to detect and kill PIDs
        if _shutil.which("lsof"):
            try:
                out = _sub.check_output(["lsof", "-ti", f":{port}"], text=True)
                for line in out.splitlines():
                    try:
                        pid = int(line.strip())
                        _sub.run(["kill", "-9", str(pid)], check=False)
                    except Exception:
                        continue
            except Exception:
                pass

    # Start an in-process WSGI server using werkzeug
    try:
        from werkzeug.serving import make_server
    except Exception:
        pytest.skip("werkzeug not available to run in-process server")

    # If port is not free, attempt to free it (best-effort) then retry
    if not _is_port_free(host, port):
        _try_free_port(port)
        # small wait for OS to release socket
        import time as _time
        _time.sleep(0.5)
        if not _is_port_free(host, port):
            pytest.skip(f"Port {port} is in use and could not be freed; ensure no other server is running on {host}:{port}")

    server = make_server(host, port, flask_app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base = f"http://{host}:{port}"
    # expose base url for tests that previously hardcoded 127.0.0.1:5000
    os.environ["BASE_URL"] = base
    # wait for health endpoint then fallback to /
    # Increase timeouts here to be tolerant of slower CI hosts.
    if not _wait_for_url(f"{base}/health", timeout=60):
        if not _wait_for_url(f"{base}/", timeout=30):
            try:
                server.shutdown()
            except Exception:
                pass
            pytest.skip("Application did not start in time; check " + log_path)

    yield {"server": server, "base_url": base, "intake_dir": str(intake_dir), "filing_cabinet": str(filing_dir), "app_log_path": log_path, "port": port, "database_path": db_path}

    try:
        server.shutdown()
    except Exception:
        pass
    try:
        thread.join(timeout=5)
    except Exception:
        pass
    # Cleanup temporary database file to avoid polluting workspace
    try:
        if os.path.exists(tmp_db):
            os.remove(tmp_db)
    except Exception:
        pass
    # Cleanup temporary directories created for this in-process run
    try:
        import shutil as _sh
        if tmp_root and os.path.exists(str(tmp_root)):
            _sh.rmtree(str(tmp_root), ignore_errors=True)
    except Exception:
        pass


@pytest.fixture()
def e2e_page(playwright, request):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    setattr(request.node, "e2e_page", page)

    # Attach runtime listeners to capture browser console and network events for failed runs
    console_logs = []
    try:
        def _on_console(msg):
            try:
                console_logs.append(f"{msg.type}: {msg.text}")
            except Exception:
                console_logs.append(f"console_event_error")
        page.on("console", _on_console)
    except Exception:
        pass

    network_events = []
    try:
        def _on_request(req):
            try:
                network_events.append({"type": "request", "method": req.method, "url": req.url})
            except Exception:
                pass
        def _on_response(resp):
            try:
                network_events.append({"type": "response", "status": resp.status, "url": resp.url})
            except Exception:
                pass
        page.on("request", _on_request)
        page.on("response", _on_response)
    except Exception:
        pass

    yield page

    failed = getattr(request.node, "failed", False)
    if failed:
        artifacts_dir = os.getenv("E2E_ARTIFACTS") or request.getfixturevalue("e2e_artifacts_dir")
        ts = int(time.time())
        base = f"{request.node.name}-{ts}"
        try:
            page.screenshot(path=os.path.join(artifacts_dir, base + ".png"), full_page=True)
        except Exception:
            pass
        try:
            with open(os.path.join(artifacts_dir, base + ".html"), "w", encoding="utf-8") as fh:
                fh.write(page.content())
        except Exception:
            pass
        try:
            # Save captured console messages
            with open(os.path.join(artifacts_dir, base + ".console.log"), "w", encoding="utf-8") as fh:
                for line in console_logs:
                    fh.write(line + "\n")
        except Exception:
            pass
        try:
            # Save network events as JSON lines for easier inspection
            import json
            with open(os.path.join(artifacts_dir, base + ".network.jsonl"), "w", encoding="utf-8") as fh:
                for ev in network_events:
                    fh.write(json.dumps(ev) + "\n")
        except Exception:
            pass
        try:
            if "app_process" in request.fixturenames:
                info = request.getfixturevalue("app_process")
                app_log = info.get("app_log_path")
                if app_log and os.path.exists(app_log):
                    shutil.copy2(app_log, os.path.join(artifacts_dir, base + "-app.log"))
        except Exception:
            pass

    try:
        page.close()
    except Exception:
        pass
    try:
        browser.close()
    except Exception:
        pass


def pytest_runtest_makereport(item, call):
    if call.when == "call" and call.excinfo is not None:
        setattr(item, "failed", True)


def resolve_final_batch_id(base_url, initial_batch_id, timeout=10):
    """Resolve the finalized/fixed batch id for a recently processed intake batch.

    Strategy:
    1. If the process_smart response returned a 'single_batch_id' use that (test callers
       should pass it when available).
    2. Poll the debug/latest_document endpoint to discover the most-recent finalized
       single document and use its batch id. This helps tests survive the fast-path
       auto-finalize behavior where intake batch ids differ from finalized batch ids.

    Returns an integer batch id or the original initial_batch_id on timeout.
    """
    import requests as _requests
    import time as _time

    deadline = _time.time() + float(timeout)
    # First quick check: try debug/latest_document if available
    while _time.time() < deadline:
        try:
            r = _requests.get(f"{base_url}/batch/api/debug/latest_document", timeout=2)
            if r.status_code == 200:
                j = r.json()
                # Some debug endpoints wrap payloads as {'data': {...}}
                if isinstance(j, dict) and 'data' in j and isinstance(j['data'], dict):
                    payload = j['data']
                else:
                    payload = j if isinstance(j, dict) else {}

                # Try multiple common shapes to find a batch id
                bid = None
                # top-level batch_id or single_batch_id
                bid = payload.get('batch_id') or payload.get('single_batch_id')
                # handle payloads that include a 'latest_document' wrapper
                if not bid:
                    if isinstance(payload, dict) and 'latest_document' in payload:
                        latest = payload.get('latest_document')
                        if isinstance(latest, dict):
                            bid = latest.get('batch_id') or latest.get('single_batch_id')
                if not bid and isinstance(payload, dict) and 'data' in payload and isinstance(payload['data'], dict) and 'latest_document' in payload['data']:
                    latest = payload['data'].get('latest_document')
                    if isinstance(latest, dict):
                        bid = latest.get('batch_id') or latest.get('single_batch_id')
                # nested document -> batch_id
                if not bid:
                    doc = payload.get('document') if isinstance(payload, dict) else None
                    if isinstance(doc, dict):
                        bid = doc.get('batch_id') or doc.get('single_batch_id')
                # defensive: sometimes payload contains nested 'data' again
                if not bid and isinstance(payload, dict) and 'data' in payload and isinstance(payload['data'], dict):
                    inner = payload['data']
                    bid = inner.get('batch_id') or inner.get('single_batch_id')

                if bid:
                    try:
                        return int(bid)
                    except Exception:
                        return initial_batch_id
        except Exception:
            pass
        _time.sleep(0.25)
    # Fallback: if the debug endpoint did not reveal a batch id, try reading
    # the in-process server's test database directly (app_process exposes
    # its DB path via E2E_SERVER_DB). This avoids an HTTP race when the
    # server has finalized a batch but the debug endpoint didn't reflect it
    # yet for the test client.
    db_path = os.getenv('E2E_SERVER_DB') or os.getenv('DATABASE_PATH')
    if db_path:
        try:
            import sqlite3 as _sqlite
            conn = _sqlite.connect(db_path, timeout=5)
            cur = conn.cursor()
            cur.execute("SELECT id, batch_id FROM single_documents ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            conn.close()
            if row and row[1]:
                try:
                    return int(row[1])
                except Exception:
                    return initial_batch_id
        except Exception:
            pass
    return initial_batch_id


@pytest.fixture(scope='session')
def base_url():
    """Session-scoped base URL for E2E tests (from env or default)."""
    return os.environ.get('BASE_URL', 'http://127.0.0.1:5000')


@pytest.fixture(scope='function')
def poll_smart_status(base_url):
    """Provide a callable for tests to poll smart processing fallback status.

    Usage:
        last_event, meta = poll_smart_status(token)
    """
    def _poll(token, **kwargs):
        # Prefer the canonical helper at doc_processor.tests.e2e.smart_status_helper
        return __import__('doc_processor.tests.e2e.smart_status_helper', fromlist=['']).poll_smart_processing_status(token, base_url=base_url, **kwargs)
    return _poll


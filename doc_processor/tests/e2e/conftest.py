import os
import subprocess
import time
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"


@pytest.fixture(scope="session", autouse=True)
def ensure_artifacts_dir():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
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


@pytest.fixture(scope="session")
def e2e_artifacts_dir(tmp_path_factory):
    env_dir = os.getenv("E2E_ARTIFACTS_DIR") or os.getenv("E2E_ARTIFACTS")
    if env_dir:
        os.makedirs(env_dir, exist_ok=True)
        return str(env_dir)

    repo_root = Path(__file__).resolve().parents[3]
    artifacts = repo_root / "doc_processor" / "tests" / "e2e" / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    return str(artifacts)


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
    os.environ["FAST_TEST_MODE"] = "1"
    os.environ["SKIP_OLLAMA"] = "1"
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
    if not _wait_for_url(f"{base}/health", timeout=30):
        if not _wait_for_url(f"{base}/", timeout=15):
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


@pytest.fixture()
def e2e_page(playwright, request):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    setattr(request.node, "e2e_page", page)
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


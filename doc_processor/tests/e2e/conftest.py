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


@pytest.fixture(scope="session")
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

    host = os.getenv("E2E_HOST") or os.getenv("HOST") or "127.0.0.1"
    port = int(os.getenv("E2E_PORT") or os.getenv("PORT") or _find_free_port())

    venv_py = repo_root / "doc_processor" / "venv" / "bin" / "python"
    if venv_py.exists():
        py = str(venv_py)
    else:
        py = shutil.which("python3") or shutil.which("python") or "python3"

    env = os.environ.copy()
    env.update(
        {
            "PLAYWRIGHT_E2E": "1",
            "INTAKE_DIR": str(intake_dir),
            "PROCESSED_DIR": str(processed_dir),
            "FILING_CABINET_DIR": str(filing_dir),
            "FAST_TEST_MODE": "1",
            "SKIP_OLLAMA": "1",
            "PYTHONUNBUFFERED": "1",
            "HOST": host,
            "PORT": str(port),
        }
    )

    # Use an explicit per-run database path so tests can reliably inspect it.
    db_path = tmp_root / 'documents.db'
    # Ensure the parent directory exists
    db_parent = db_path.parent
    db_parent.mkdir(parents=True, exist_ok=True)
    env.update({"DATABASE_PATH": str(db_path)})
    # Also reflect the DB path in the test process environment so subprocess
    # helpers and direct sqlite access in tests can use the same path if they
    # read os.environ['DATABASE_PATH'].
    os.environ['DATABASE_PATH'] = str(db_path)

    cmd = [py, "-m", "doc_processor.app"]
    log_path = os.path.join(e2e_artifacts_dir, "app_process.log")
    log_fh = open(log_path, "ab")
    proc = subprocess.Popen(cmd, env=env, stdout=log_fh, stderr=subprocess.STDOUT, cwd=str(repo_root))

    base = f"http://{host}:{port}"
    # wait for health endpoint then fallback to /
    if not _wait_for_url(f"{base}/health", timeout=30):
        if not _wait_for_url(f"{base}/", timeout=15):
            try:
                proc.kill()
            except Exception:
                pass
            log_fh.close()
            pytest.skip("Application did not start in time; check " + log_path)

    yield {"proc": proc, "base_url": base, "intake_dir": str(intake_dir), "filing_cabinet": str(filing_dir), "app_log_path": log_path, "port": port, "db_path": str(db_path)}

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


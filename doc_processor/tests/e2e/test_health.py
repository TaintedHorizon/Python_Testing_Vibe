import os
import time
import requests


def test_root_health():
    """Simple health check for the running app.

    This test expects the application to be running on 127.0.0.1:5000.
    It will retry for a short period to allow the server to start.
    """
    url = os.environ.get("E2E_URL", "http://127.0.0.1:5000/")
    deadline = time.time() + 30
    last_status = None
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=2)
            last_status = resp.status_code
            if resp.status_code in (200, 302):
                return
        except Exception:
            last_status = None
        time.sleep(1)
    assert last_status in (200, 302), f"App did not respond with 200/302 within timeout, last status={last_status}"

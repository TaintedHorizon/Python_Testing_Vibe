import os
import requests


def test_root_contains_title():
    """Assert the app root contains the site title.

    Uses the same E2E_URL env var as the other E2E tests.
    """
    url = os.environ.get("E2E_URL", "http://127.0.0.1:5000/")
    resp = requests.get(url, timeout=5)
    assert resp.status_code in (200, 302)
    body = resp.text
    assert "Document Processor" in body, "Expected 'Document Processor' in root HTML"

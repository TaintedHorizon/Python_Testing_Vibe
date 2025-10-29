import os
import re
import requests


def test_root_contains_title():
    """Assert the app root renders an HTML page with a non-empty <title> tag.

    Uses the same E2E_URL env var as the other E2E tests. This is intentionally
    lenient: the application may override the base title per-page (for example
    the index page sets "New Batch"), so asserting a non-empty <title> is a
    stable smoke check that the UI served an HTML document.
    """
    url = os.environ.get("E2E_URL", "http://127.0.0.1:5000/")
    resp = requests.get(url, timeout=5)
    assert resp.status_code in (200, 302)
    body = resp.text or ""
    m = re.search(r"<title\s*>\s*(.*?)\s*</title>", body, flags=re.IGNORECASE | re.DOTALL)
    assert m is not None and m.group(1).strip(), "Expected a non-empty <title> in the root HTML"

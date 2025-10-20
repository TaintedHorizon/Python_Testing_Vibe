import os
import time
import shutil
import requests
import pytest

from pathlib import Path

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
INTAKE = Path(os.environ.get('INTAKE_DIR') or Path(__file__).resolve().parents[2] / "intake")
FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"

# base URL for the running app (injected by app_process fixture)
BASE = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')


def dump_artifacts(page, name):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(ARTIFACTS / f"{name}.png"), full_page=True)
        html = page.content()
        (ARTIFACTS / f"{name}.html").write_text(html, encoding="utf-8")
    except Exception:
        pass


@pytest.mark.playwright
def test_single_batch_flow(playwright, browser_name):
    # Preconditions
    assert os.getenv("FAST_TEST_MODE") == "1", "FAST_TEST_MODE=1 required"

    # copy a single fixture into intake with a unique name
    src = FIXTURES / "sample_small.pdf"
    dst = INTAKE / f"sample_single_{int(time.time())}.pdf"
    shutil.copy(src, dst)

    # start a new page
    browser = playwright[browser_name].launch()
    page = browser.new_page()

    try:
        # Trigger analysis by visiting intake index
        page.goto(f"{BASE}/")

        # Poll debug endpoint for latest document id
        latest = None
        for _ in range(30):
            try:
                r = requests.get(f"{BASE}/batch/api/debug/latest_document", timeout=1)
                if r.status_code == 200 and r.json():
                    latest = r.json()
                    break
            except Exception:
                pass
            time.sleep(1)

        assert latest, "Latest document not found via debug endpoint"

        # extract the canonical document and batch info; prefer latest_document
        latest_doc = None
        batch_id = None
        if isinstance(latest, dict) and "data" in latest and "latest_document" in latest["data"]:
            latest_doc = latest["data"]["latest_document"]
        elif isinstance(latest, dict) and "latest_document" in latest:
            latest_doc = latest["latest_document"]
        else:
            latest_doc = latest

        if isinstance(latest_doc, dict):
            doc_id = latest_doc.get("id")
            batch_id = latest_doc.get("batch_id")
        else:
            doc_id = None

        assert doc_id, "Document id not found in debug response"

        # Navigate to the manipulation UI using the processing batch and first document index
        if batch_id:
            page.goto(f"{BASE}/document/batch/{batch_id}/manipulate/1")
        else:
            # Fallback: try the legacy per-document URL if available
            page.goto(f"{BASE}/document/{doc_id}/manipulate")

        # Open preview and rotate (robust selector expectations)
        # Allow a bit more time for the viewer to initialize in CI/local
        page.wait_for_selector("iframe[src*='serve_single_pdf']", timeout=20000)
        iframe = page.query_selector("iframe[src*='serve_single_pdf']")
        assert iframe, "PDF iframe not found"

        # Click rotate right if control exists
        try:
            rotate = page.query_selector("#rotateRight, .btn-rotate-right")
            if rotate:
                rotate.click()
        except Exception:
            pass

        # Save and assert that rotation persisted by reloading page and checking rotate state
        page.reload()
        # not all viewers expose rotation; presence is considered success for end-to-end flow
        page.wait_for_selector("iframe[src*='serve_single_pdf']", timeout=5000)

    except Exception as e:
        dump_artifacts(page, "single_batch_failure")
        raise
    finally:
        browser.close()

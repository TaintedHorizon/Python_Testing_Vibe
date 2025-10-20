import os
import time
import shutil
import requests
import pytest

from pathlib import Path
import os

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
# NOTE: compute INTAKE at runtime inside the test so the app_process fixture
# (which sets INTAKE_DIR) can run first. See app_process autouse session fixture.
FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def dump_artifacts(page, name):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(ARTIFACTS / f"{name}.png"), full_page=True)
        html = page.content()
        (ARTIFACTS / f"{name}.html").write_text(html, encoding="utf-8")
    except Exception:
        pass


@pytest.mark.playwright
def test_group_batch_flow(playwright, browser_name):
    assert os.getenv("FAST_TEST_MODE") == "1", "FAST_TEST_MODE=1 required"

    files = ["sample_small.pdf", "sample_small.pdf"]
    # determine intake path from env (set by app_process fixture) or repo fallback
    intake_path = Path(os.environ.get('INTAKE_DIR') or Path(__file__).resolve().parents[2] / "intake")
    # copy into intake with unique target names so files don't overwrite each other
    for i, fname in enumerate(files, start=1):
        src = FIXTURES / fname
        dst = intake_path / f"sample_small_{i}.pdf"
        shutil.copy(src, dst)

    # Wait for the app_process intake directory to notice the files (filesystem sync/latency)
    seen = False
    for _ in range(10):
        try:
            listing = [p.name for p in intake_path.iterdir() if p.is_file()]
            if any(n.startswith('sample_small_') for n in listing):
                seen = True
                break
        except Exception:
            pass
        time.sleep(0.25)
    assert seen, f"Intake dir {intake_path} does not contain the copied fixtures: {list(intake_path.iterdir()) if intake_path.exists() else 'dir missing'}"

    base = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')

    browser = playwright[browser_name].launch()
    page = browser.new_page()

    try:
        page.goto(f"{base}/")

        try:
            r = requests.post(f"{base}/batch/process_smart", timeout=2)
            token = r.json().get("token") if r.status_code == 200 else None
        except Exception:
            token = None

        batch = None
        for _ in range(30):
            try:
                r = requests.get(f"{base}/batch/api/debug/latest_document", timeout=1)
                if r.status_code == 200 and r.json():
                    latest = r.json()
                    if isinstance(latest, dict) and "data" in latest and "latest_document" in latest["data"]:
                        doc = latest["data"]["latest_document"]
                    elif isinstance(latest, dict) and "latest_document" in latest:
                        doc = latest["latest_document"]
                    else:
                        doc = latest
                    batch = doc.get("batch_id") if isinstance(doc, dict) else None
                    if batch:
                        break
            except Exception:
                pass
            time.sleep(1)
        # after polling loop
        assert batch, "Batch not found for grouped intake"

        page.goto(f"{base}/batch/{batch}/manipulate")

        # Wait for any manipulation UI to appear: either per-document manipulate links,
        # the manipulation toolbar/panel, or the PDF iframe used for previews.
        page.wait_for_selector("a[href*='manipulate'], #manipulationToolbar, .manipulation-panel, iframe[src*='serve_single_pdf']", timeout=15000)

    except Exception:
        dump_artifacts(page, "group_batch_failure")
        raise
    finally:
        browser.close()

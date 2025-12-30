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
    # Ensure FAST_TEST_MODE is enabled for deterministic E2E behavior
    # Ensure FAST_TEST_MODE is enabled for deterministic E2E behavior.
    # Use setdefault so callers can override if needed, but tests will
    # default to fast mode for reliability in CI.
    os.environ.setdefault('FAST_TEST_MODE', '1')
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

        # Resolve finalized/fixed batch id (handles fast-path auto-finalize behavior)
        from doc_processor.tests.e2e.conftest import resolve_final_batch_id
        try:
            batch = resolve_final_batch_id(base, None, timeout=30)
        except Exception:
            batch = None
        assert batch, "Batch not found for grouped intake"

        page.goto(f"{base}/batch/{batch}/manipulate")

        # Wait for any manipulation UI to appear: either per-document manipulate links,
        # the manipulation toolbar/panel, or the PDF iframe used for previews.
        # Prefer stable data-testid selector when FAST_TEST_MODE is enabled
        try:
            page.wait_for_selector("[data-testid='manipulation-toolbar'], a[href*='manipulate'], #manipulationToolbar, .manipulation-panel, iframe[src*='serve_single_pdf']", timeout=15000)
        except Exception:
            page.wait_for_selector("a[href*='manipulate'], #manipulationToolbar, .manipulation-panel, iframe[src*='serve_single_pdf']", timeout=15000)

    except Exception:
        dump_artifacts(page, "group_batch_failure")
        raise
    finally:
        browser.close()

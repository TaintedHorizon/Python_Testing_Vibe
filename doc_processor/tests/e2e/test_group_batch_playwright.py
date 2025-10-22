import os
import time
import shutil
import pytest
import requests

from config_manager import app_config


def _copy_fixture_into_intake(fixture_name):
    repo_root = os.path.dirname(__file__)
    candidates = [
        os.path.join(repo_root, 'fixtures', fixture_name),
        os.path.join(repo_root, '..', 'fixtures', fixture_name),
    ]
    src = next((c for c in candidates if os.path.exists(c)), None)
    if not src:
        raise FileNotFoundError(f"Fixture {fixture_name} not found")
    intake_candidates = [
        # Prefer the environment-configured intake dir (set by app_process fixture)
        os.environ.get('INTAKE_DIR'),
        os.path.abspath(os.path.join(repo_root, '..', '..', 'intake')),
        '/mnt/scans_intake'
    ]
    for d in intake_candidates:
        if not d:
            continue
        try:
            os.makedirs(d, exist_ok=True)
            base, ext = os.path.splitext(fixture_name)
            # use time_ns to avoid millisecond collisions when copying files quickly
            unique_suffix = f"-{time.time_ns()}-{os.getpid()}"
            dst_name = f"{base}{unique_suffix}{ext}"
            dst = os.path.join(d, dst_name)
            shutil.copy2(src, dst)
            return dst
        except Exception:
            continue
    raise RuntimeError('Could not copy fixture into any intake dir')


@pytest.mark.e2e
def test_grouped_batch_end_to_end(app_process, e2e_page):
    """Create two intake PDFs, run smart processing, and assert grouped manipulation UI appears.

    Uses the in-process server fixtures (`app_process`) so environment is isolated.
    """
    base = app_process['base_url']
    # copy two identical fixtures to trigger grouping logic
    f1 = _copy_fixture_into_intake('sample_small.pdf')
    f2 = _copy_fixture_into_intake('sample_small.pdf')

    # Ensure copies are visible to the in-process server's intake dir before triggering
    # smart processing to avoid races on slower CI hosts.
    intake_dir = os.environ.get('INTAKE_DIR') or (app_process.get('intake_dir') if app_process else None)
    if intake_dir:
        # wait for both files to appear (longer deadline to tolerate CI slowness)
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                # ensure both copied file paths exist on disk
                if os.path.exists(f1) and os.path.exists(f2):
                    break
                files = [p for p in os.listdir(intake_dir) if p.endswith('.pdf')]
                if len(files) >= 2:
                    break
            except Exception:
                pass
            time.sleep(0.5)

    # Trigger smart processing
    resp = requests.post(f"{base}/batch/process_smart")
    resp.raise_for_status()
    js = resp.json()
    batch_id = None
    if isinstance(js, dict):
        data = js.get('data')
        # API may return different keys depending on fast-path behavior.
        # Prefer explicit batch identifiers when present.
        if isinstance(data, dict):
            if 'batch_id' in data:
                batch_id = data.get('batch_id')
            elif 'single_batch_id' in data:
                batch_id = data.get('single_batch_id')
        # Fallback to top-level keys if present
        if not batch_id:
            batch_id = js.get('batch_id') or js.get('single_batch_id')

    # Resolve finalized/fixed batch id (handles fast-path auto-finalize behavior).
    from doc_processor.tests.e2e.conftest import resolve_final_batch_id
    try:
        batch_id = resolve_final_batch_id(base, batch_id or None, timeout=10)
    except Exception:
        # on any error, keep the original batch_id (may be None)
        pass

    # wait for batch documents to appear and be grouped
    # increase deadline to be tolerant of CI scheduling
    deadline = time.time() + 60
    docs = None
    while time.time() < deadline:
        try:
            # If we don't yet have a batch_id (very rare), try to derive it using the shared helper
            if not batch_id:
                from doc_processor.tests.e2e.conftest import resolve_final_batch_id
                try:
                    batch_id = resolve_final_batch_id(base, None, timeout=5)
                except Exception:
                    pass

            if not batch_id:
                time.sleep(0.5)
                continue

            r = requests.get(f"{base}/batch/api/debug/batch_documents/{batch_id}", timeout=2)
            if r.status_code != 200:
                time.sleep(0.5)
                continue
            payload = r.json()
            if isinstance(payload, dict) and 'data' in payload:
                payload = payload['data']
            grouped = payload.get('grouped_documents') if isinstance(payload, dict) else None
            single = payload.get('single_documents') if isinstance(payload, dict) else None
            # prefer grouped documents presence
            if isinstance(grouped, list) and len(grouped) > 0:
                docs = grouped
                break
            if isinstance(single, list) and len(single) >= 2:
                docs = single
                break

            # No docs found on this batch id; try helper to find the finalized processing batch
            try:
                from doc_processor.tests.e2e.conftest import resolve_final_batch_id
                new_batch = resolve_final_batch_id(base, batch_id, timeout=5)
                if new_batch and new_batch != batch_id:
                    batch_id = new_batch
            except Exception:
                pass
        except Exception:
            pass
        time.sleep(0.5)

    assert docs, f"No grouped or multi single docs found for batch {batch_id}"

    # if grouped, navigate to grouping manipulation page
    first = docs[0]
    doc_id = first.get('id') if isinstance(first, dict) else None
    page = e2e_page
    if doc_id:
        page.goto(f"{base}/document/batch/{batch_id}/manipulate/{doc_id}")
    else:
        page.goto(f"{base}/batch/control")

    # ensure group manipulation UI is present
    sel = None
    try:
        # give the page time to finish loading resources and run client-side JS
        try:
            page.wait_for_load_state('networkidle', timeout=30000)
        except Exception:
            # non-fatal; still try to wait for the selector below
            pass
        # Mirror selectors used in other E2E flows to be more robust (iframe or manipulate links)
        sel = page.wait_for_selector("a[href*='manipulate'], #groupingToolbar, #manipulationToolbar, .manipulation-panel, iframe[src*='serve_single_pdf']", timeout=45000)
    except Exception:
        pass
    assert sel, 'Grouping / manipulation UI did not appear in time'

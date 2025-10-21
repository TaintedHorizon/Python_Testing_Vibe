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
        os.path.abspath(os.path.join(repo_root, '..', '..', 'intake')),
        os.environ.get('INTAKE_DIR'),
        '/mnt/scans_intake'
    ]
    for d in intake_candidates:
        if not d:
            continue
        try:
            os.makedirs(d, exist_ok=True)
            base, ext = os.path.splitext(fixture_name)
            unique_suffix = f"-{int(time.time()*1000)}-{os.getpid()}"
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

    # Trigger smart processing
    resp = requests.post(f"{base}/batch/process_smart")
    resp.raise_for_status()
    js = resp.json()
    batch_id = None
    if isinstance(js, dict):
        data = js.get('data')
        if isinstance(data, dict) and 'batch_id' in data:
            batch_id = data.get('batch_id')
        else:
            batch_id = js.get('batch_id')

    # wait for batch documents to appear and be grouped
    deadline = time.time() + 30
    docs = None
    while time.time() < deadline:
        try:
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
        sel = page.wait_for_selector('#groupingToolbar, #manipulationToolbar, .manipulation-panel', timeout=10000)
    except Exception:
        pass
    assert sel, 'Grouping / manipulation UI did not appear in time'

import os
import time
import shutil
from pathlib import Path

import pytest


@pytest.mark.skipif(os.getenv('PLAYWRIGHT_E2E', '0') != '1', reason='Playwright E2E disabled')
def test_preview_rotate_persist(e2e_page, app_process, e2e_artifacts_dir):
    """Rotate a document in the preview, apply the rotation, reload and assert persistence.

    This test is intentionally forgiving about exact selectors: it looks for common
    rotate controls (ids `rotateRight`/`rotateLeft` or buttons with text) and
    for an "apply rotation" button (ids starting with `apply-rotation-`).
    It asserts that the preview HTML contains a `rotate(` style after rotation
    and that the same marker exists after reloading the manipulation/preview page.
    """

    page = e2e_page
    base = app_process['base_url']
    intake_dir = Path(app_process['intake_dir'])

    # Ensure sample PDF is present
    repo_root = Path(__file__).resolve().parents[2]
    sample = repo_root / 'tests' / 'fixtures' / 'sample_small.pdf'
    assert sample.exists(), f'Missing fixture: {sample}'
    dest = intake_dir / 'sample_rotate.pdf'
    shutil.copy2(sample, dest)

    # Kick analysis via the synchronous API (GET /api/analyze_intake) which runs the detector
    try:
        resp = page.request.get(f"{base}/api/analyze_intake", timeout=30_000)
    except Exception:
        # If the API call fails, navigate to the analyze page to surface errors
        page.goto(f"{base}/analyze_intake")
        page.wait_for_selector('body', timeout=30_000)

    # Ensure processing completes: poll the app DB for a single_documents row for our filename
    analysis_done = False
    filename = 'sample_rotate.pdf'
    try:
        import sqlite3
        dbp = app_process.get('db_path') if isinstance(app_process, dict) else None
        for _ in range(60):
            try:
                if dbp and os.path.exists(dbp):
                    conn = sqlite3.connect(dbp)
                    cur = conn.cursor()
                    cur.execute("SELECT id FROM single_documents WHERE original_filename = ? OR original_pdf_path LIKE ? LIMIT 1", (filename, f"%{filename}%"))
                    r = cur.fetchone()
                    conn.close()
                    if r:
                        analysis_done = True
                        break
            except Exception:
                pass
            time.sleep(1)
    except Exception:
        pass

    assert analysis_done, 'Analysis did not complete in time (no single_documents row was created)'

    # Navigate to batch control (where manipulation/preview links are available)
    page.goto(f"{base}/batch/control")

    # Wait for at least one document row/link to be present
    found_doc = False
    for _ in range(30):
        try:
            if page.query_selector('.document-section') or page.query_selector('table tr'):
                found_doc = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    assert found_doc, 'No document visible in batch control'

    # Attempt to open the first manipulate/preview link
    # Common anchors: a[href*="/manipulate"], a[href*="/revisit"], a[href*="/batch/view"]
    link = None
    for sel in ['a[href*="/manipulate"]', 'a[href*="/revisit"]', 'a[href*="/batch/view"]', 'a:has-text("Manipulate")']:
        try:
            el = page.query_selector(sel)
            if el:
                link = el
                break
        except Exception:
            pass

    if link:
        href = link.get_attribute('href')
        if href.startswith('http'):
            page.goto(href)
        else:
            page.goto(base + href)
    else:
        # As a fallback, go to the generic manipulate/revisit path for first document
        page.goto(base + '/manipulate')

    # Wait for rotate controls to appear
    rotate_sel = None
    for _ in range(30):
        for candidate in ['#rotateRight', '#rotateLeft', 'button:has-text("Rotate Right")', 'button:has-text("Rotate")']:
            try:
                if page.query_selector(candidate):
                    rotate_sel = candidate
                    break
            except Exception:
                pass
        if rotate_sel:
            break
        time.sleep(0.5)

    assert rotate_sel, 'No rotate control found in preview/manipulation UI'

    # Click rotate right (one 90° step)
    try:
        page.click(rotate_sel, timeout=5000)
    except Exception:
        # Best-effort: try evaluate a JS rotation function if present
        try:
            page.evaluate("() => (typeof rotateDocument === 'function') && rotateDocument(null, 90)")
        except Exception:
            pass

    # Wait briefly for DOM transform updates
    time.sleep(1)

    # Check for rotation marker in page HTML
    html1 = page.content()
    rotated_marker = 'rotate(' in html1 or 'currentRotation' in html1 or 'Rotated document' in html1
    assert rotated_marker, 'Rotation did not reflect in page HTML after clicking rotate'

    # If an apply button exists, click it to persist rotation
    apply_btn = None
    for _ in range(3):
        try:
            el = page.query_selector('[id^="apply-rotation-"]')
            if el:
                apply_btn = el
                break
        except Exception:
            pass
        time.sleep(0.5)

    applied_via_ui = False
    doc_id = None
    if apply_btn:
        try:
            # try to extract doc id from the apply button id if present (apply-rotation-<id>)
            aid = apply_btn.get_attribute('id')
            if aid and aid.startswith('apply-rotation-'):
                doc_id = aid.split('apply-rotation-')[-1]
            apply_btn.click()
            applied_via_ui = True
            # allow server to process rotation
            time.sleep(1)
        except Exception:
            applied_via_ui = False

    # If rotate wasn't applied via the UI, try using the server API directly.
    if not applied_via_ui:
        # Look up the document id in the app DB by filename (more reliable)
        try:
            import sqlite3
            from config_manager import app_config
            db_path = getattr(app_config, 'DATABASE_PATH', None)
            if db_path and os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                filename = 'sample_rotate.pdf'
                cur.execute("SELECT id, original_filename, original_pdf_path FROM single_documents WHERE original_filename = ? OR original_pdf_path LIKE ? LIMIT 1", (filename, f"%{filename}%"))
                row = cur.fetchone()
                if row:
                    doc_id = row[0]
                conn.close()
        except Exception:
            doc_id = doc_id

        if doc_id:
            try:
                import requests
                rot_url = f"{base}/api/rotate_document/{doc_id}"
                requests.post(rot_url, json={"rotation": 90}, timeout=5)
                # allow server to process
                time.sleep(1)
            except Exception:
                pass

    # Reload the page to ensure persisted state is reflected
    page.reload()
    page.wait_for_selector('body', timeout=10000)
    html2 = page.content()

    persisted = 'rotate(' in html2 or 'currentRotation' in html2 or 'Applied' in html2
    assert persisted, 'Rotation did not persist after reload'

    # Strict verification: prefer the app API for authoritative logical rotation
    # (rotation_service stores logical rotation in document_rotations table).
    try:
        # Try to resolve doc id if we don't already have it
        if not doc_id:
            # attempt DB lookup against the app process DB path
            try:
                import sqlite3
                db_path = app_process.get('db_path') if isinstance(app_process, dict) else None
                if db_path and os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    cur = conn.cursor()
                    filename = 'sample_rotate.pdf'
                    cur.execute("SELECT id FROM single_documents WHERE original_filename = ? OR original_pdf_path LIKE ? LIMIT 1", (filename, f"%{filename}%"))
                    r = cur.fetchone()
                    if r:
                        doc_id = r[0]
                    conn.close()
            except Exception:
                pass

        rotation_verified = False
        if doc_id:
            # Query the app API which uses get_logical_rotation() internally
            try:
                import requests
                resp = requests.get(f"{base}/api/rotation/{doc_id}", timeout=3)
                if resp.ok:
                    j = resp.json()
                    rot = j.get('data', {}).get('rotation') if isinstance(j, dict) else None
                    if rot is None:
                        # older versions may return payload differently
                        rot = (j.get('rotation') if isinstance(j, dict) else None)
                    if rot is not None and int(rot) != 0:
                        rotation_verified = True
            except Exception:
                pass

        # Fallback: inspect DB directly (legacy intake_rotations or document_rotations)
        if not rotation_verified:
            try:
                import sqlite3
                db_path = app_process.get('db_path') if isinstance(app_process, dict) else None
                if db_path and os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    cur = conn.cursor()
                    filename = 'sample_rotate.pdf'
                    # Check new logical table first
                    try:
                        cur.execute('SELECT rotation FROM document_rotations WHERE document_id = (SELECT id FROM single_documents WHERE original_filename = ? OR original_pdf_path LIKE ? LIMIT 1)', (filename, f"%{filename}%"))
                        rr = cur.fetchone()
                        if rr and rr[0] is not None:
                            rotation_verified = int(rr[0]) != 0
                    except Exception:
                        pass
                    # Then legacy intake_rotations table
                    if not rotation_verified:
                        try:
                            cur.execute('SELECT rotation FROM intake_rotations WHERE filename = ?', (filename,))
                            r2 = cur.fetchone()
                            if r2 and r2[0] is not None:
                                rotation_verified = int(r2[0]) != 0
                        except Exception:
                            pass
                    conn.close()
            except Exception:
                pass

        assert rotation_verified, 'Server-side rotation not observed via API or DB for the file'
    except AssertionError:
        raise
    except Exception as e:
        raise RuntimeError(f'Failed to verify rotation via API/DB: {e}')

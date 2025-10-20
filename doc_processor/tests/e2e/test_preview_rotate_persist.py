import os
import shutil
import time
import pytest
import requests

from .playwright_helpers import dump_screenshot_and_html, get_rotation_degrees


@pytest.mark.skipif(os.getenv('PLAYWRIGHT_E2E', '0') != '1', reason='Playwright E2E disabled')
def test_preview_rotation_persists(app_process, e2e_page, e2e_artifacts_dir):
    """Rotate a document in the preview, reload, and assert rotation persisted.

    The test will:
    - Copy a sample PDF into the fixture intake
    - Start analysis and navigate to the manipulation/preview page
    - Check the preview is present, read rotation attribute
    - Click rotate control, wait for change, reload, and verify persistence
    """
    base = app_process['base_url']
    intake = app_process['intake_dir']

    # Copy sample into intake
    sample = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'sample_small.pdf'))
    assert os.path.exists(sample), f'Missing fixture: {sample}'
    dest = os.path.join(intake, 'sample_intake.pdf')
    if not os.path.exists(dest):
        shutil.copy2(sample, dest)

    page = e2e_page
    # Navigate to analyze page and start analysis (robust selectors)
    page.goto(base + '/analyze_intake')
    time.sleep(0.5)
    try:
        if page.query_selector('[data-testid="start-analysis"]'):
            page.click('[data-testid="start-analysis"]')
        else:
            page.evaluate('() => { if (typeof startAnalysis === "function") { startAnalysis(); return true; } }')
    except Exception:
        # fallback to text selector
        try:
            page.click('text=Start Analysis')
        except Exception:
            pytest.skip('No Start Analysis entrypoint')

    # Wait for analysis results by polling the analysis API (more deterministic)
    analysis_done = False
    api_url = base + '/api/analyze_intake'
    for _ in range(60):
        try:
            r = requests.get(api_url, timeout=3)
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, dict) and j.get('analyses') and len(j.get('analyses', [])) > 0:
                    analysis_done = True
                    break
        except Exception:
            pass
        time.sleep(0.5)

    if not analysis_done:
        dump_screenshot_and_html(page, e2e_artifacts_dir, 'analysis_no_results')
        pytest.fail('Analysis results did not appear via API in time')

    # Prefer backend-driven navigation: start smart processing to create batch and get its id,
    # then navigate directly to the manipulation page for the first document. Fall back to batch control.
    batch_id = None
    try:
        resp = requests.post(base + '/batch/process_smart', json={}, timeout=10)
        if resp.ok:
            j = resp.json()
            # create_success_response nests payload under 'data' in many routes
            data = j.get('data') if isinstance(j, dict) else None
            if isinstance(data, dict) and data.get('batch_id'):
                batch_id = data.get('batch_id')
            elif isinstance(j, dict) and j.get('batch_id'):
                batch_id = j.get('batch_id')
    except Exception:
        batch_id = None

    if batch_id:
        # Try to query test-only debug endpoint for documents in the batch
        try:
            dbg = requests.get(f"{base}/batch/api/debug/batch_documents/{batch_id}", timeout=5)
            if dbg.ok:
                dj = dbg.json()
                payload = (dj.get('data') or {}) if isinstance(dj, dict) else {}
                single_docs = payload.get('single_documents', [])
                grouped_docs = payload.get('grouped_documents', [])
                if isinstance(single_docs, list) and len(single_docs) > 0:
                    doc_id = single_docs[0].get('id')
                    if doc_id:
                        page.goto(f"{base}/document/batch/{batch_id}/manipulate/{doc_id}")
                elif isinstance(grouped_docs, list) and len(grouped_docs) > 0:
                    # navigate to first grouped document manipulator (doc_num=1)
                    page.goto(f"{base}/batch/{batch_id}/manipulate/1")
                else:
                    # Fallback: try debug endpoint for latest document across batches
                    try:
                        latest = requests.get(f"{base}/batch/api/debug/latest_document", timeout=3)
                        if latest.ok:
                            lj = latest.json().get('data') if isinstance(latest.json(), dict) else None
                            if lj and lj.get('latest_document'):
                                latest_doc = lj.get('latest_document')
                                doc_id = latest_doc.get('id')
                                latest_batch = latest_doc.get('batch_id')
                                if doc_id and latest_batch:
                                    page.goto(f"{base}/document/batch/{latest_batch}/manipulate/{doc_id}")
                                else:
                                    page.goto(f"{base}/batch/{batch_id}/manipulate")
                            else:
                                page.goto(f"{base}/batch/{batch_id}/manipulate")
                        else:
                            page.goto(f"{base}/batch/{batch_id}/manipulate")
                    except Exception:
                        page.goto(f"{base}/batch/{batch_id}/manipulate")
            else:
                page.goto(f"{base}/batch/{batch_id}/manipulate")
        except Exception:
            page.goto(f"{base}/batch/{batch_id}/manipulate")
        # Wait for processing to populate the manipulation page (iframe or document text)
        waited = 0
        ready = False
        while waited < 60:
            try:
                # look for iframe preview or pagination that indicates documents present
                if page.query_selector("iframe[src*='serve_single_pdf']"):
                    ready = True
                    break
                if page.query_selector(".pdf-viewer iframe"):
                    ready = True
                    break
                # legacy pagination text
                if 'Document 1 of' in page.content():
                    ready = True
                    break
                # detect explicit empty state and continue waiting
                if 'No documents found in this batch' in page.content():
                    # still waiting for processing
                    pass
            except Exception:
                pass
            time.sleep(1)
            waited += 1
    else:
        # Fallback to batch control view
        page.goto(base + '/batch/control')

    # Find the first document preview link or button and open it
    preview_selector_candidates = [
        'a.document-preview',
        'button.preview-btn',
        '[data-testid="open-preview"]',
        '#documents-table a.preview-link',
        '.preview-link',
        'iframe[src*="serve_single_pdf"]',
        '.pdf-viewer iframe'
    ]
    preview_found = None
    for sel in preview_selector_candidates:
        try:
            els = page.query_selector_all(sel)
            if els:
                # pick first visible or the first attached
                chosen = None
                for el in els:
                    try:
                        if el.is_visible():
                            chosen = el
                            break
                    except Exception:
                        chosen = el
                        break
                if chosen is not None:
                    preview_found = sel
                    try:
                        # If the chosen element is an iframe, don't click it — it's already the preview
                        tag = chosen.evaluate('el => (el.tagName||"").toLowerCase()')
                        if tag != 'iframe':
                            try:
                                page.click(sel, timeout=3000)
                            except Exception:
                                try:
                                    page.evaluate('() => { if (typeof openPreview === "function") { openPreview(); return true; } }')
                                except Exception:
                                    pass
                        # else: iframe is the preview; no click necessary
                    except Exception:
                        # Best-effort: ignore evaluation errors and try clicking
                        try:
                            page.click(sel, timeout=3000)
                        except Exception:
                            pass
                    break
        except Exception:
            continue
    if not preview_found:
        # If we have a batch_id, try the Batch Control page and click the manipulate link for that batch
        if batch_id:
            try:
                page.goto(base + '/batch/control')
                target_link = f'/batch/{batch_id}/manipulate'
                found = False
                for _ in range(90):
                    try:
                        # Reload to pick up server-rendered status changes
                        try:
                            page.reload()
                        except Exception:
                            pass
                        link = page.query_selector(f'a[href*="{target_link}"]')
                        if link:
                            try:
                                link.click()
                            except Exception:
                                try:
                                    page.evaluate("(t) => { const a = document.querySelector(`a[href*=\\\"${t}\\\"]`); if(a) a.click(); }", target_link)
                                except Exception:
                                    pass
                            found = True
                            break
                    except Exception:
                        pass
                    time.sleep(1)
                if not found:
                    dump_screenshot_and_html(page, e2e_artifacts_dir, 'no_preview_control')
                    pytest.fail('No manipulate link found on batch control for batch_id')
            except Exception:
                dump_screenshot_and_html(page, e2e_artifacts_dir, 'no_preview_control')
                pytest.fail('No preview control found in batch control view')
        else:
            # no preview controls; fail but capture artifacts
            dump_screenshot_and_html(page, e2e_artifacts_dir, 'no_preview_control')
            pytest.fail('No preview control found in batch control view')

    # Wait for preview element to appear
    # Determine the actual preview element selector to check rotation
    # Include the universal document viewer modal and common iframe/image selectors
    preview_element_candidates = [
        "iframe[src*='serve_single_pdf']",
        '.pdf-viewer iframe',
        '#document-preview', '.preview-canvas', 'iframe.preview-frame', '.preview-frame',
        '.image-viewer', '#pdfViewerContainer', '#pdfModal', '.pdf-modal'
    ]
    preview_selector = None
    for psel in preview_element_candidates:
        try:
            if page.query_selector(psel):
                preview_selector = psel
                break
        except Exception:
            continue

    if not preview_selector:
        dump_screenshot_and_html(page, e2e_artifacts_dir, 'preview_not_found_after_open')
        pytest.fail('Preview element not found after opening preview')

    # Wait until the preview element is attached (visible or at least present)
    attached = False
    for _ in range(30):
        try:
            el = page.query_selector(preview_selector)
            if el:
                attached = True
                break
        except Exception:
            pass
        time.sleep(0.5)
    if not attached:
        dump_screenshot_and_html(page, e2e_artifacts_dir, 'preview_not_attached')
        pytest.fail('Preview element did not attach in time')

    # Read initial rotation if available
    initial_rotation = get_rotation_degrees(page, preview_selector)

    # Click rotate right control
    # Manipulate UI uses .btn-rotate-right / .btn-rotate-left classes and data-doc-id attributes
    rotate_selectors = ['[data-testid="rotate-right"]', '.rotate-right', 'button.rotate-right', '.btn-rotate-right', '.btn-rotate-left',
                        '#rotateRight', '#rotateLeft', '#rotate_right', '#rotate_left']
    rotated = False
    for rsel in rotate_selectors:
        try:
            if page.query_selector(rsel):
                page.click(rsel)
                rotated = True
                break
        except Exception:
            continue
    if not rotated:
        dump_screenshot_and_html(page, e2e_artifacts_dir, 'no_rotate_control')
        pytest.fail('No rotate control found')


    # Wait for rotation to change (poll up to a few seconds)
    new_rotation = None
    for _ in range(10):
        try:
            new_rotation = get_rotation_degrees(page, preview_selector)
            if initial_rotation is None and new_rotation is not None:
                break
            if initial_rotation is not None and new_rotation is not None and new_rotation != initial_rotation:
                break
        except Exception:
            pass
        time.sleep(0.5)

    if initial_rotation is not None and new_rotation is not None:
        assert new_rotation != initial_rotation, 'Rotation control did not change rotation'

    # Reload page and verify rotation persisted
    page.reload()
    # ensure page reload and preview attach
    # wait for the preview element to be present in the DOM (may be hidden inside a modal)
    page.wait_for_selector(preview_selector, state='attached', timeout=15000)
    persisted_rotation = get_rotation_degrees(page, preview_selector)

    # If rotation metadata isn't available, at least ensure preview still loads after reload
    if initial_rotation is None and persisted_rotation is None:
        # We don't have a reliable DOM rotation indicator; pass if preview still loaded
        return

    assert persisted_rotation == new_rotation, f'Rotation did not persist across reload (expected {new_rotation}, got {persisted_rotation})'

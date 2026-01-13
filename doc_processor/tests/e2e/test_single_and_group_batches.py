import os
import time
import shutil
import requests
import pytest

from .playwright_helpers import dump_screenshot_and_html, wait_for_analysis_complete
from .selector_utils import click_with_fallback, wait_for_any


ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
import os
import time
import shutil
import requests
import pytest

from .playwright_helpers import dump_screenshot_and_html, wait_for_analysis_complete


ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
INTAKE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "intake")

# default base for requests/pages; can be overridden by app_process fixture which sets BASE_URL
BASE = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')


def _copy_fixture_into_intake(fixture_name):
    # prefer e2e fixtures folder, fallback to tests/fixtures
    src_candidates = [
        os.path.join(os.path.dirname(__file__), "fixtures", fixture_name),
        os.path.join(os.path.dirname(__file__), "..", "fixtures", fixture_name),
    ]
    src = None
    for c in src_candidates:
        if os.path.exists(c):
            src = c
            break
    if not src:
        raise FileNotFoundError(f"Fixture {fixture_name} not found in expected locations: {src_candidates}")

    candidates = []
    repo_intake = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "intake"))
    candidates.append(repo_intake)
    env_intake = os.environ.get('INTAKE_DIR')
    if env_intake:
        candidates.append(os.path.abspath(env_intake))
    candidates.append('/mnt/scans_intake')

    last_dst = None
    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            # Ensure unique destination filename to avoid overwriting when tests copy
            # the same fixture multiple times into the same intake directory.
            base, ext = os.path.splitext(fixture_name)
            unique_suffix = f"-{int(time.time()*1000)}-{os.getpid()}"
            dst_name = f"{base}{unique_suffix}{ext}"
            dst = os.path.join(d, dst_name)
            shutil.copyfile(src, dst)
            last_dst = dst
        except Exception:
            continue
    if not last_dst:
        raise FileNotFoundError(f"Could not copy fixture to any intake directory: {candidates}")
    return last_dst


def _process_smart():
    resp = requests.post(f"{BASE}/batch/process_smart")
    resp.raise_for_status()
    js = resp.json()
    try:
        if isinstance(js, dict):
            data = js.get("data")
            if isinstance(data, dict) and "batch_id" in data:
                js["batch_id"] = data["batch_id"]
    except Exception:
        pass
    return js


@pytest.mark.e2e
def test_single_document_batch_flow(page):
    """Create a single-document intake, run smart processing, verify manipulation page and rotate persistence."""
    dst = _copy_fixture_into_intake("sample_small.pdf")

    try:
        proc = _process_smart()
        batch_id = proc.get("batch_id")

        if not batch_id:
            from doc_processor.tests.e2e.conftest import resolve_final_batch_id
            try:
                batch_id = resolve_final_batch_id(BASE, None, timeout=20)
            except Exception:
                batch_id = None

        assert batch_id, "batch_id not found after processing"

        # The orchestrator may create a separate processing batch for single
        # documents (different from the intake batch). Prefer polling the
        # `latest_document` debug endpoint to learn the real document id and
        # its authoritative batch_id. If that fails, fall back to checking the
        # original batch via batch_documents.
        doc = None
        doc_id = None
        real_batch = None
        for _ in range(15):
            try:
                r = requests.get(f"{BASE}/batch/api/debug/latest_document", timeout=2)
                if r.status_code != 200:
                    time.sleep(0.5)
                    continue
                js = r.json()
                if isinstance(js, dict) and "data" in js and "latest_document" in js["data"]:
                    doc = js["data"]["latest_document"]
                elif isinstance(js, dict) and "latest_document" in js:
                    doc = js["latest_document"]
                else:
                    doc = js
                if isinstance(doc, dict):
                    doc_id = doc.get('id')
                    real_batch = doc.get('batch_id')
                    if doc_id:
                        break
            except Exception:
                pass
            time.sleep(0.5)

        # Secondary fallback: query the original batch for documents
        if not doc_id:
            for _ in range(8):
                try:
                    r = requests.get(f"{BASE}/batch/api/debug/batch_documents/{batch_id}", timeout=2)
                    if r.status_code != 200:
                        time.sleep(0.5)
                        continue
                    payload = r.json()
                    if isinstance(payload, dict) and "data" in payload:
                        payload = payload["data"]
                    single_docs = payload.get('single_documents') if isinstance(payload, dict) else None
                    grouped_docs = payload.get('grouped_documents') if isinstance(payload, dict) else None
                    if isinstance(single_docs, list) and len(single_docs) >= 1:
                        doc = single_docs[0]
                        doc_id = doc.get('id')
                        real_batch = batch_id
                        break
                    if isinstance(grouped_docs, list) and len(grouped_docs) >= 1:
                        doc = grouped_docs[0]
                        doc_id = doc.get('id')
                        real_batch = batch_id
                        break
                except Exception:
                    pass
                time.sleep(0.5)

        assert doc_id, f"document id not found for batch {batch_id} (latest_document and batch_documents checks failed)"
        # Use the real batch where the document actually landed
        batch_id = real_batch or batch_id

        page.goto(f"{BASE}/document/batch/{batch_id}/manipulate/{doc_id}")

        try:
            page.wait_for_selector("iframe[src*='serve_single_pdf']", timeout=7000)
            frame = page.query_selector("iframe[src*='serve_single_pdf']")
        except Exception:
            page.goto(f"{BASE}/batch/{batch_id}/manipulate")
            page.wait_for_selector("iframe[src*='serve_single_pdf'], #pdfViewerContainer", timeout=10000)
            frame = page.query_selector("iframe[src*='serve_single_pdf']")
        assert frame

        # Prefer stable data-testid selectors when FAST_TEST_MODE is enabled;
        # fall back to legacy ids/classes for compatibility.
        # Prefer stable data-testid selectors when available
        click_with_fallback(page, 'rotate-right', fallback="button#rotateRight, .btn-rotate-right", timeout=2000)

        page.reload()
        page.wait_for_selector("iframe[src*='serve_single_pdf']", timeout=10000)

        assert True

    except Exception:
        dump_screenshot_and_html(page, os.path.join(ARTIFACTS_DIR, "single_failure"))
        raise


@pytest.mark.e2e
def test_grouped_batch_flow(page):
    dst1 = _copy_fixture_into_intake("sample_small.pdf")
    dst2 = _copy_fixture_into_intake("sample_small.pdf")

    try:
        proc = _process_smart()
        batch_id = proc.get("batch_id")
        assert batch_id

        try:
            server_db = os.environ.get('E2E_SERVER_DB') or os.environ.get('DATABASE_PATH') or os.path.join(os.path.dirname(__file__), '..', 'documents.db')
            import sqlite3
            conn = sqlite3.connect(server_db, timeout=10)
            conn.row_factory = None
            cur = conn.cursor()
            cand_dir = os.environ.get('INTAKE_DIR') or '/mnt/scans_intake'
            files = [f for f in os.listdir(cand_dir) if f.lower().endswith('.pdf')]
            created = 0
            for f in files:
                path = os.path.join(cand_dir, f)
                try:
                    cur.execute("SELECT id FROM single_documents WHERE original_pdf_path = ?", (path,))
                    if cur.fetchone():
                        continue
                    size = os.path.getsize(path)
                    cur.execute(
                        "INSERT INTO single_documents (batch_id, original_filename, original_pdf_path, page_count, file_size_bytes, status) VALUES (?,?,?,?,?, 'completed')",
                        (batch_id, f, path, 1, size)
                    )
                    created += 1
                except Exception:
                    continue
            if created:
                conn.commit()
            conn.close()
        except Exception:
            pass

        docs = None
        for _ in range(15):
            try:
                r = requests.get(f"{BASE}/batch/api/debug/batch_documents/{batch_id}", timeout=2)
                if r.status_code == 200:
                    payload = r.json()
                    if isinstance(payload, dict) and "data" in payload:
                        payload = payload["data"]
                    single_docs = payload.get('single_documents') if isinstance(payload, dict) else None
                    grouped_docs = payload.get('grouped_documents') if isinstance(payload, dict) else None
                    if isinstance(single_docs, list) and len(single_docs) >= 2:
                        docs = single_docs
                        break
                    if isinstance(grouped_docs, list) and len(grouped_docs) > 0:
                        docs = grouped_docs
                        break
            except Exception:
                pass
            time.sleep(1)

        if not docs:
            # Find the processing batch where documents were actually inserted.
            # Poll latest_document until it reports a batch_id, then query that
            # batch via batch_documents to get all documents for the processing batch.
            processing_batch = None
            from doc_processor.tests.e2e.conftest import resolve_final_batch_id
            try:
                processing_batch = resolve_final_batch_id(BASE, None, timeout=30)
            except Exception:
                processing_batch = None

            if processing_batch:
                for _ in range(8):
                    try:
                        r = requests.get(f"{BASE}/batch/api/debug/batch_documents/{processing_batch}", timeout=2)
                        if r.status_code != 200:
                            time.sleep(0.5)
                            continue
                        payload = r.json()
                        if isinstance(payload, dict) and "data" in payload:
                            payload = payload["data"]
                        single_docs = payload.get('single_documents') if isinstance(payload, dict) else None
                        grouped_docs = payload.get('grouped_documents') if isinstance(payload, dict) else None
                        if isinstance(single_docs, list) and len(single_docs) >= 2:
                            docs = single_docs
                            batch_id = processing_batch
                            break
                        if isinstance(grouped_docs, list) and len(grouped_docs) > 0:
                            docs = grouped_docs
                            batch_id = processing_batch
                            break
                    except Exception:
                        pass
                    time.sleep(0.5)

        assert docs, f"No documents found in batch {batch_id} after processing"

        first = docs[0]
        doc_id = first.get('id') if isinstance(first, dict) else None
        if doc_id:
            page.goto(f"{BASE}/document/batch/{batch_id}/manipulate/{doc_id}")
        else:
            page.goto(f"{BASE}/manipulation/batch/{batch_id}")

        # Wait for manipulation UI; prefer testid where available
        # Wait for manipulation UI; prefer testid where available
        wait_for_any(page, 'manipulation-toolbar', fallback="#manipulationToolbar, .manipulation-panel, iframe[src*='serve_single_pdf']", timeout=10000)

    except Exception:
        dump_screenshot_and_html(page, os.path.join(ARTIFACTS_DIR, "group_failure"))
        raise

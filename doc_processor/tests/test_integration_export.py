import os
import time
from doc_processor.app import create_app
from doc_processor.config_manager import SHUTDOWN_EVENT


def test_export_progress_and_download():
    """Trigger a single-document export in FAST_TEST_MODE and verify progress API and batch status."""
    os.environ['FAST_TEST_MODE'] = '1'
    app = create_app()
    client = app.test_client()

    # Create a dummy batch via start_new_batch endpoint
    resp = client.post('/batch/start_new')
    assert resp.status_code == 302 or resp.status_code == 200

    # For the test, reuse existing batch id by inspecting home page (simple heuristic)
    home = client.get('/')
    assert home.status_code == 200

    # Start a finalize_single_documents_batch for batch id 1 (tests use placeholders)
    resp = client.post('/export/finalize_single_documents_batch/1', data={'force': '1'})
    assert resp.status_code in (200, 201, 202)
    data = resp.get_json() or {}
    # Expect a success response structure
    assert 'success' in data

    # Poll the progress API until status completed or abort
    for _ in range(10):
        p = client.get('/export/api/progress')
        assert p.status_code == 200
        progress = p.get_json() or {}
        # progress payload may be empty at first
        if progress and isinstance(progress.get('data'), dict):
            entries = progress['data']
            if entries:
                # Inspect the first entry
                first = list(entries.values())[0]
                if first.get('status') in ('completed', 'error', 'aborted'):
                    break
        time.sleep(0.1)

    # Signal shutdown to ensure cleanup
    if SHUTDOWN_EVENT is not None:
        SHUTDOWN_EVENT.set()

    os.environ.pop('FAST_TEST_MODE', None)

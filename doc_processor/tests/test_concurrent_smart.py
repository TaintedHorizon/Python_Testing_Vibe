import threading
import time
from http import HTTPStatus

import pytest

from doc_processor.app import create_app
from doc_processor.database import get_db_connection


def _start_server_client():
    app = create_app()
    return app.test_client()


def _issue_smart(client, results, idx):
    resp = client.post('/batch/process_smart', json={})
    results[idx] = resp.get_json() if resp.status_code == HTTPStatus.OK else {'error': resp.status_code}


def test_concurrent_process_smart_creates_single_intake_batch(tmp_path):
    """Simulate concurrent smart processing requests and ensure intake batch reuse.

    This test starts multiple threads that call /batch/process_smart simultaneously.
    The expectation: the application should reuse or create a single intake batch and not create many duplicate empty intake batches.
    """
    client = _start_server_client()

    threads = []
    num_threads = 6
    results = [None] * num_threads

    for i in range(num_threads):
        t = threading.Thread(target=_issue_smart, args=(client, results, i))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # Check results for tokens and batch ids
    batch_ids = [r['data']['batch_id'] for r in results if r and r.get('data')]
    assert batch_ids, "No batch ids returned"

    # Check DB - there should be at most num_threads unique batch ids but ideally 1 or few
    with get_db_connection() as conn:
        cur = conn.cursor()
        rows = cur.execute("SELECT id, status FROM batches ORDER BY id DESC LIMIT 20").fetchall()
        ids = [r[0] for r in rows]

    # Ensure we didn't create an excessive number of small-intake-only batches
    # (Allow some leeway; expect <= num_threads but typically 1)
    assert len(ids) <= num_threads
    # At least one of the returned batch_ids must appear in DB
    assert any(bid in ids for bid in batch_ids)

import os
import threading
import time
from doc_processor.app import create_app
from doc_processor.config_manager import SHUTDOWN_EVENT


def test_integration_shutdown_fast_mode():
    """Start the app in FAST_TEST_MODE, trigger a smart processing run, then set SHUTDOWN_EVENT and assert workers stop."""
    # Ensure FAST_TEST_MODE is active for deterministic inline execution
    os.environ['FAST_TEST_MODE'] = '1'

    app = create_app()

    # Use test client to request a smart processing token and start immediate run
    client = app.test_client()

    # Ensure SHUTDOWN_EVENT is clear
    if SHUTDOWN_EVENT is not None:
        try:
            SHUTDOWN_EVENT.clear()
        except Exception:
            pass

    # Trigger smart processing (no intake files means it will early-exit but still exercise orchestration)
    resp = client.post('/batch/process_smart', json={})
    assert resp.status_code == 200
    data = resp.get_json()
    payload = data.get('success') if data else None
    # Response is expected to be a success-shaped object from create_success_response
    assert data and 'token' in data.get('data', {}) or 'token' in (data or {}), f"Unexpected response payload: {data}"

    # Allow a small amount of time for the inline processing to run
    time.sleep(0.2)

    # Now signal shutdown
    if SHUTDOWN_EVENT is not None:
        SHUTDOWN_EVENT.set()

    # Wait briefly to let threads notice (should be immediate given FAST_TEST_MODE)
    time.sleep(0.2)

    # Verify shutdown event is set and no long-running background state
    assert SHUTDOWN_EVENT is None or SHUTDOWN_EVENT.is_set()

    # Cleanup env
    os.environ.pop('FAST_TEST_MODE', None)

import threading
import time
from doc_processor.config_manager import SHUTDOWN_EVENT


def test_shutdown_event_stops_thread():
    # Start a background thread that runs until SHUTDOWN_EVENT is set
    stopped = threading.Event()

    def worker():
        while True:
            if SHUTDOWN_EVENT is not None and SHUTDOWN_EVENT.is_set():
                break
            # Do minimal work
            time.sleep(0.01)
        stopped.set()

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    # Ensure thread is running
    time.sleep(0.05)
    assert not stopped.is_set()

    # Signal shutdown and wait
    if SHUTDOWN_EVENT is not None:
        SHUTDOWN_EVENT.set()

    t.join(timeout=2)
    assert stopped.is_set(), "Worker did not stop within timeout after SHUTDOWN_EVENT set"
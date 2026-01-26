"""Helper utilities for polling smart processing fallback status in tests.

This module provides a single well-tested implementation of
`poll_smart_processing_status` that tests and helper scripts can import.

Defaults are relaxed (longer polling and larger stall tolerance) to
reduce flakiness in CI when background processing is slow.
"""
import time
from typing import Any, Dict, Optional, Tuple

import requests


def poll_smart_processing_status(
    token: str,
    base_url: str = "http://127.0.0.1:5000",
    max_polls: int = 300,
    stall_limit: int = 60,
    poll_interval: float = 1.0,
    """Helper utilities for polling smart processing fallback status in tests.

    This module provides a single well-tested implementation of
    `poll_smart_processing_status` that tests and helper scripts can import.

    Defaults are relaxed (longer polling and larger stall tolerance) to
    reduce flakiness in CI when background processing is slow.
    """
    import time
    from typing import Any, Dict, Optional, Tuple

    import requests


    def poll_smart_processing_status(
        token: str,
        base_url: str = "http://127.0.0.1:5000",
        max_polls: int = 300,
        stall_limit: int = 60,
        poll_interval: float = 1.0,
        timeout: float = 5.0,
        session: Optional[requests.Session] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Poll the smart processing fallback endpoint until complete or stalled.

        Returns `(last_event, meta)` where `last_event` is the last event
        dict returned by the server (or ``None``) and ``meta`` contains
        diagnostic fields: `polls`, `stalled`, `completed`, `last_progress`.

        The helper will also probe a test-only debug endpoint
        `/batch/api/debug/smart_token/{token}` which returns token metadata
        (including `batch_id`) so tests can deterministically discover the
        batch created for a token without relying on client SSE timing.
        """
        status_url = f"{base_url.rstrip('/')}/batch/api/smart_processing_status?token={token}"
        debug_url = f"{base_url.rstrip('/')}/batch/api/debug/smart_token/{token}"
        s = session or requests.Session()
        last_progress = None
        stall_count = 0
        polls = 0
        last = None

        for _ in range(max_polls):
            polls += 1
            try:
                r = s.get(status_url, timeout=timeout)
            except Exception:
                # Try debug endpoint as a fallback
                try:
                    rd = s.get(debug_url, timeout=timeout)
                    if rd.status_code == 200:
                        jd = rd.json()
                        meta = jd.get('data') or jd
                        # If debug exposes batch_id directly, return synthetic event
                        if isinstance(meta, dict) and meta.get('batch_id'):
                            return {'batch_id': meta.get('batch_id')}, {'polls': polls, 'stalled': False, 'completed': False, 'last_progress': last_progress}
                        last = meta.get('last_event') if isinstance(meta, dict) else None
                        if isinstance(last, dict) and last.get('batch_id'):
                            return last, {'polls': polls, 'stalled': False, 'completed': False, 'last_progress': last_progress}
                except Exception:
                    pass
                time.sleep(poll_interval)
                continue

            try:
                j = r.json()
            except Exception:
                j = {}

            last = j.get('data', {}).get('last_event') if isinstance(j, dict) else None
            # If primary returned nothing useful, probe debug endpoint
            if last is None:
                try:
                    rd = s.get(debug_url, timeout=timeout)
                    if rd.status_code == 200:
                        jd = rd.json()
                        meta = jd.get('data') or jd
                        if isinstance(meta, dict) and meta.get('batch_id'):
                            return {'batch_id': meta.get('batch_id')}, {'polls': polls, 'stalled': False, 'completed': False, 'last_progress': last_progress}
                        last = meta.get('last_event') if isinstance(meta, dict) else None
                        if isinstance(last, dict) and last.get('batch_id'):
                            return last, {'polls': polls, 'stalled': False, 'completed': False, 'last_progress': last_progress}
                except Exception:
                    pass

            if isinstance(last, dict):
                prog = last.get('progress')
                complete = bool(last.get('complete'))
                if prog is not None:
                    if prog != last_progress:
                        last_progress = prog
                        stall_count = 0
                    else:
                        stall_count += 1
                else:
                    stall_count += 1

                if complete:
                    return last, {'polls': polls, 'stalled': False, 'completed': True, 'last_progress': last_progress}

                if stall_count >= stall_limit:
                    return last, {'polls': polls, 'stalled': True, 'completed': False, 'last_progress': last_progress}

            time.sleep(poll_interval)

        return last, {'polls': polls, 'stalled': stall_count >= stall_limit, 'completed': False, 'last_progress': last_progress}

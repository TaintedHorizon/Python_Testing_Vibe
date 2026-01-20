"""Helper utilities for polling smart processing fallback status in tests.

Provides `poll_smart_processing_status` which repeatedly polls the
`/batch/api/smart_processing_status` endpoint until processing completes
or progress stalls.
"""
import time
import requests
from typing import Any, Dict, Optional, Tuple


def poll_smart_processing_status(token: str, base_url: str = 'http://127.0.0.1:5000',
                                 max_polls: int = 60, stall_limit: int = 10,
                                 poll_interval: float = 1.0, timeout: float = 5.0,
                                 session: Optional[requests.Session] = None) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Poll the smart processing fallback endpoint until complete or stalled.

    Returns a tuple `(last_event, meta)` where `last_event` is the last
    `last_event` dict returned by the server (or None) and `meta` contains
    diagnostic info: `polls`, `stalled`, `completed`, `last_progress`.
    """
    status_url = f"{base_url.rstrip('/')}/batch/api/smart_processing_status?token={token}"
    s = session or requests.Session()
    last_progress = None
    stall_count = 0
    polls = 0
    for attempt in range(max_polls):
        polls += 1
        try:
            r = s.get(status_url, timeout=timeout)
        except Exception as e:
            # Return diagnostic info but continue polling until max
            time.sleep(poll_interval)
            continue
        try:
            j = r.json()
        except Exception:
            j = {}
        last = j.get('data', {}).get('last_event') if isinstance(j, dict) else None
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
    return last if 'last' in locals() else None, {'polls': polls, 'stalled': stall_count >= stall_limit, 'completed': False, 'last_progress': last_progress}

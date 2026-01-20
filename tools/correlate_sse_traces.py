#!/usr/bin/env python3
import re
import sys
from datetime import datetime

APP_LOG = '/tmp/e2e_logs/app_process_59573.log'
TRACER = '/tmp/e2e_logs/playwright_tracer_59573.out'

sse_re = re.compile(r"SSE\[(?P<label>[^\]]+)\] emit ts=(?P<ts>[0-9]+\.[0-9]+) payload=(?P<payload>.*)")

events = []

# Parse app log SSE emits
try:
    with open(APP_LOG, 'r') as f:
        for line in f:
            m = sse_re.search(line)
            if m:
                ts = float(m.group('ts'))
                label = m.group('label')
                payload = m.group('payload').strip()
                events.append((ts, 'server', 'SSE_EMIT', label, payload))
except FileNotFoundError:
    print('App log not found:', APP_LOG, file=sys.stderr)

# Parse tracer lines (timestamped)
try:
    with open(TRACER, 'r') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line.strip():
                continue
            parts = line.split(' ', 1)
            try:
                ts = float(parts[0])
                msg = parts[1] if len(parts) > 1 else ''
            except Exception:
                # Fallback: no leading timestamp
                ts = None
                msg = line
            src = 'client'
            typ = 'LOG'
            detail = msg
            # classify
            if msg.startswith('REQFAILED:'):
                typ = 'REQFAILED'
            elif msg.startswith('REQ:'):
                typ = 'REQ'
            elif msg.startswith('RESP:'):
                typ = 'RESP'
            elif 'API poll error' in msg:
                typ = 'API_POLL_ERR'
            elif msg.startswith('CONSOLE:'):
                typ = 'CONSOLE'
            elif 'process_smart status' in msg:
                typ = 'PROCESS_SMART'
            events.append((ts if ts is not None else 0.0, src, typ, None, detail))
except FileNotFoundError:
    print('Tracer output not found:', TRACER, file=sys.stderr)

# Sort by timestamp (None/0 at start)
events.sort(key=lambda e: e[0])

# Print timeline
print('Timestamp (epoch) | ISO8601 | source | type | label | detail')
for ev in events:
    ts, src, typ, label, detail = ev
    try:
        iso = datetime.utcfromtimestamp(ts).isoformat() + 'Z'
    except Exception:
        iso = 'n/a'
    lab = label or ''
    print(f"{ts:.3f} | {iso} | {src} | {typ} | {lab} | {detail}")

print('\nSummary: total events =', len(events))

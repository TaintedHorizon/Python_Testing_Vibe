#!/usr/bin/env bash
set -euo pipefail

URL=${1:-http://127.0.0.1:5000/}
echo "Running simple E2E smoke against $URL"

status=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$URL" || echo "000")
if [ "$status" = "200" ] || [ "$status" = "302" ]; then
  echo "OK: $URL returned $status"
  exit 0
else
  echo "FAIL: $URL returned $status" >&2
  # show app logs if available
  if [ -f e2e_app.out ]; then
    echo "---- tail of e2e_app.out ----"
    tail -n 200 e2e_app.out || true
  fi
  exit 2
fi

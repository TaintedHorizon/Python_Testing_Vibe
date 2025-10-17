#!/usr/bin/env bash
set -euo pipefail

# scripts/run_local_e2e.sh
# Runs Playwright E2E locally against the Flask app started by ./start_app.sh

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "[run_local_e2e] Using repo root: $ROOT_DIR"

# 1) Create venv if missing and activate
if [ ! -d "doc_processor/venv" ]; then
  echo "Creating venv at doc_processor/venv"
  python3 -m venv doc_processor/venv
fi
. doc_processor/venv/bin/activate

echo "Upgrading pip and installing Python deps..."
pip install --upgrade pip
pip install -r doc_processor/requirements.txt
pip install playwright pytest-playwright

echo "Installing Playwright browsers (may require apt packages)..."
python -m playwright install --with-deps || true

# 2) Install Node deps in ui_tests
if [ -d ui_tests ] && [ -f ui_tests/package.json ]; then
  echo "Installing Node deps in ui_tests (npm ci)"
  (cd ui_tests && npm ci)
else
  echo "WARNING: ui_tests/package.json not found. Skipping npm ci."
fi

# 3) Start the Flask app in background
mkdir -p doc_processor/logs
chmod +x ./start_app.sh

# If something is already listening on :5000, do not try to start another server.
USE_EXISTING_APP=0
if ss -ltn "sport = :5000" >/dev/null 2>&1 || lsof -i :5000 >/dev/null 2>&1; then
  echo "Port 5000 already in use; will reuse existing server if reachable."
  USE_EXISTING_APP=1
fi

STARTED_BY_SCRIPT=0
if [ "$USE_EXISTING_APP" -eq 0 ]; then
  nohup ./start_app.sh > doc_processor/logs/ci_app.log 2>&1 &
  echo $! > /tmp/run_local_e2e_app.pid
  STARTED_BY_SCRIPT=1
else
  echo "Skipping start_app.sh because port 5000 is in use."
fi

echo "Waiting for app to respond on http://127.0.0.1:5000/ (60s timeout)"
for i in {1..60}; do
  if curl -sSf http://127.0.0.1:5000/ >/dev/null 2>&1; then
    echo "app is up"
    break
  fi
  echo "waiting for app... ($i)"
  sleep 1
done

if ! curl -sSf http://127.0.0.1:5000/ >/dev/null 2>&1; then
  echo "ERROR: app did not start in time. Showing last 200 lines of log:" >&2
  tail -n 200 doc_processor/logs/ci_app.log || true
  exit 1
fi

# 4) Run Playwright tests
if [ -d ui_tests ]; then
  echo "Running Playwright tests in ui_tests"
  (cd ui_tests && npx playwright test e2e --reporter=list)
else
  echo "ERROR: ui_tests directory missing; cannot run Playwright tests" >&2
  exit 1
fi

# 5) Teardown
echo "Tearing down the app and showing last 200 lines of log"
tail -n 200 doc_processor/logs/ci_app.log || true
if [ "$STARTED_BY_SCRIPT" -eq 1 ] && [ -f /tmp/run_local_e2e_app.pid ]; then
  PID=$(cat /tmp/run_local_e2e_app.pid)
  if ps -p "$PID" >/dev/null 2>&1; then
    echo "Killing app pid $PID"
    kill "$PID" || true
  else
    echo "App pid $PID not running; nothing to kill"
  fi
  rm -f /tmp/run_local_e2e_app.pid || true
else
  echo "Did not start app in this run or no pid file present; skipping kill"
fi

echo "Done." 

#!/usr/bin/env bash
set -euo pipefail

# Start the application in background for CI/E2E runs.
# Creates e2e_app.out and e2e_app.pid in the current working directory.

echo "Starting app via ./start_app.sh (CI wrapper)"
touch e2e_app.out
chmod 644 e2e_app.out

# Launch the start script in background, redirecting output to e2e_app.out
./start_app.sh > e2e_app.out 2>&1 &
echo $! > e2e_app.pid
echo "Launched app with pid $(cat e2e_app.pid). Logs -> e2e_app.out"

# Give the process a short moment to initialize
sleep 1

exit 0

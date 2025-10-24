#!/usr/bin/env bash
# Dry-run wrapper for scripts/run_local_e2e.sh
# Sets a test-safe PID path and runs the original script.

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
TEST_TMPDIR="${TEST_TMPDIR:-/tmp/python_testing_vibe_tests}"
PID_FILE="${TEST_TMPDIR}/run_local_e2e_app.pid"

export RUN_LOCAL_E2E_PID_FILE="${PID_FILE}"

exec "${ROOT_DIR}/scripts/run_local_e2e.sh" "$@"

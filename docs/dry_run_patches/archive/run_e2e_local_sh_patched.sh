#!/usr/bin/env bash
# Dry-run wrapper for scripts/run_e2e_local.sh
# Ensures any pid/artifact paths are under TEST_TMPDIR then runs original.

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
TEST_TMPDIR="${TEST_TMPDIR:-/tmp/python_testing_vibe_tests}"

export E2E_ARTIFACTS_DIR="${TEST_TMPDIR}/e2e_artifacts"
export RUN_E2E_PID_FILE="${TEST_TMPDIR}/run_e2e_app.pid"

exec "${ROOT_DIR}/scripts/run_e2e_local.sh" "$@"

#!/usr/bin/env bash
# Dry-run wrapper for scripts/run_e2e_wrapper.sh
# Force artifact dirs into TEST_TMPDIR for CI/test safety and exec original.

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
TEST_TMPDIR="${TEST_TMPDIR:-/tmp/python_testing_vibe_tests}"

export E2E_WRAPPER_ARTIFACTS="${TEST_TMPDIR}/e2e_wrapper_artifacts"

exec "${ROOT_DIR}/scripts/run_e2e_wrapper.sh" "$@"

#!/usr/bin/env bash
# Dry-run wrapper for scripts/sanitize_workflows.sh
# Force any temporary or output dirs into TEST_TMPDIR.

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
TEST_TMPDIR="${TEST_TMPDIR:-/tmp/python_testing_vibe_tests}"

export SANITIZE_OUTPUT_DIR="${TEST_TMPDIR}/sanitize_workflows"

exec "${ROOT_DIR}/scripts/sanitize_workflows.sh" "$@"

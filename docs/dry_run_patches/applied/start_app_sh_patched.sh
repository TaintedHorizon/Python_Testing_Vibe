#!/usr/bin/env bash
# Dry-run wrapper for repository `start_app.sh`.
# Sets TEST_TMPDIR and related defaults so test runs don't touch user venvs or state.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export ROOT_DIR

: "${TEST_TMPDIR:=/tmp/python_testing_vibe_tests}"
export TEST_TMPDIR

# Ensure test-scoped venv and logs directories exist
mkdir -p "${TEST_TMPDIR}/venv"
mkdir -p "${TEST_TMPDIR}/logs"

# Delegate to original startup script with TEST_TMPDIR set
exec "${ROOT_DIR}/start_app.sh" "$@"

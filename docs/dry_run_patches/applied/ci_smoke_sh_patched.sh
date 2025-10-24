#!/usr/bin/env bash
# Dry-run wrapper for `ci/smoke.sh`.
# Ensures TEST_TMPDIR is set for CI-local smoke runs delegated from docs.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export ROOT_DIR

: "${TEST_TMPDIR:=/tmp/python_testing_vibe_tests}"
export TEST_TMPDIR

mkdir -p "${TEST_TMPDIR}/logs"

# Delegate to original CI smoke script
exec "${ROOT_DIR}/ci/smoke.sh" "$@"

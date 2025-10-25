#!/usr/bin/env bash
# Dry-run wrapper for `scripts/smoke_local.sh`.
# Sets TEST_TMPDIR-safe defaults and calls the original script.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export ROOT_DIR

# Prefer existing TEST_TMPDIR, otherwise create/use a repo-scoped temp dir
: "${TEST_TMPDIR:=/tmp/python_testing_vibe_tests}"
export TEST_TMPDIR

# Ensure a test-scoped logs directory
mkdir -p "${TEST_TMPDIR}/logs"

# Delegate to the original script but with TEST_TMPDIR and ROOT_DIR set.
exec "${ROOT_DIR}/scripts/smoke_local.sh" "$@"

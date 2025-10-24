#!/usr/bin/env bash
# Dry-run wrapper for `tools/repo_organize.sh`.
# Routes any file operations into TEST_TMPDIR by setting a repo-rooted TMPBASE.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export ROOT_DIR

# Default TEST_TMPDIR if not set
: "${TEST_TMPDIR:=/tmp/python_testing_vibe_tests}"
export TEST_TMPDIR

# Provide a safe repo tmp base used by the script
export REPO_ORGANIZE_TMPBASE="${TEST_TMPDIR}/repo_organize"
mkdir -p "${REPO_ORGANIZE_TMPBASE}"

# Delegate to the original script
exec "${ROOT_DIR}/tools/repo_organize.sh" "$@"

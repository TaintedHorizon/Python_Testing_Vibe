#!/usr/bin/env bash
# ci/check_test_tmpdir.sh
# Fails if TEST_TMPDIR is not set or is located inside the repository root.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEST_TMPDIR_VAL="${TEST_TMPDIR:-}"

if [ -z "${TEST_TMPDIR_VAL}" ]; then
  echo "[ci/check_test_tmpdir] ERROR: TEST_TMPDIR is not set. Set TEST_TMPDIR to an absolute temp path (CI should set this)." >&2
  exit 2
fi

# Resolve real paths
TEST_TMPDIR_REAL="$(readlink -f "${TEST_TMPDIR_VAL}")"
ROOT_REAL="$(readlink -f "${ROOT_DIR}")"

# Check that TEST_TMPDIR is not inside the repo root
case "${TEST_TMPDIR_REAL}" in
  ${ROOT_REAL}* )
    echo "[ci/check_test_tmpdir] ERROR: TEST_TMPDIR (${TEST_TMPDIR_REAL}) resolves inside the repository root (${ROOT_REAL})." >&2
    echo "Please set TEST_TMPDIR to a location outside the repository (e.g. /tmp/python_testing_vibe_tests)." >&2
    exit 3
    ;;
  * )
    echo "[ci/check_test_tmpdir] OK: TEST_TMPDIR=${TEST_TMPDIR_REAL} is set and outside the repo.";
    ;;
esac

exit 0

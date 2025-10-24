#!/usr/bin/env bash
# Dry-run wrapper for scripts/purge_large_files.sh
# Redirects any output archives to TEST_TMPDIR.

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
TEST_TMPDIR="${TEST_TMPDIR:-/tmp/python_testing_vibe_tests}"

export PURGE_ARCHIVE_DIR="${TEST_TMPDIR}/purge_archives"

exec "${ROOT_DIR}/scripts/purge_large_files.sh" "$@"

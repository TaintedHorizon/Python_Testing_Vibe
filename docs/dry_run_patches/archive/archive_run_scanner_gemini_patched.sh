#!/usr/bin/env bash
# Dry-run wrapper for archive legacy scanner: Document_Scanner_Gemini_outdated/run_scanner.sh
# Routes any output to TEST_TMPDIR so tests don't modify archive content.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export ROOT_DIR

: "${TEST_TMPDIR:=/tmp/python_testing_vibe_tests}"
export TEST_TMPDIR

mkdir -p "${TEST_TMPDIR}/archive_runs/gemini"

exec "${ROOT_DIR}/archive/legacy/Document_Scanner_Gemini_outdated/run_scanner.sh" "$@"

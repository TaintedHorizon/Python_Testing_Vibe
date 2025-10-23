#!/usr/bin/env bash
# Smoke script to run a minimal test set locally under a test-scoped tempdir.
# Usage: ./scripts/smoke_local.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DOC_PROC_DIR="$ROOT_DIR/doc_processor"

# Create a per-run temp dir for tests
TEST_TMPDIR="$(mktemp -d)"
echo "Using TEST_TMPDIR=$TEST_TMPDIR"

export TEST_TMPDIR

cd "$DOC_PROC_DIR"

# Activate venv if present, otherwise run with system python. See repo README for env setup.
if [ -f venv/bin/activate ]; then
  # shellcheck source=/dev/null
  source venv/bin/activate
fi

pip install -r requirements.txt >/dev/null

echo "Running non-E2E pytest subset..."
pytest -q -k "not e2e and not playwright"

echo "Smoke run complete. TEST_TMPDIR: $TEST_TMPDIR"

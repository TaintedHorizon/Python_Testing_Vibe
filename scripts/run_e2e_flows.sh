#!/usr/bin/env bash
set -euo pipefail

# Run the two canonical E2E flows (single-document and grouped) in headed mode
# Uses repo venv and safe environment overrides. Collects artifacts into /tmp.

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
ART="/tmp/e2e_flows_$(date +%Y%m%d%H%M%S)"
mkdir -p "$ART"

export PYTHONPATH="$REPO_ROOT/doc_processor"
export FAST_TEST_MODE=1
export SKIP_OLLAMA=1
export PLAYWRIGHT_E2E=1
export PLAYWRIGHT_HEADLESS=0
# Provide a test-scoped temp dir and DB so the app does not touch user-local DBs
export TEST_TMPDIR="$ART/test_tmp"
mkdir -p "$TEST_TMPDIR"
export DATABASE_PATH="$ART/documents.db"
export ALLOW_NEW_DB=1

echo "Artifacts will be written to: $ART"

VENV_PY="$REPO_ROOT/doc_processor/venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  echo "Venv python not found at $VENV_PY" >&2
  exit 1
fi

run_test(){
  local test=$1
  echo "Running: $test"
  "$VENV_PY" -m pytest "$test" -q 2>&1 | tee "$ART/$(basename "$test").log" || true
}

# canonical tests
run_test doc_processor/tests/e2e/test_single_and_group_batches.py::test_single_document_batch_flow
run_test doc_processor/tests/e2e/test_single_and_group_batches.py::test_grouped_batch_flow

echo "Collecting playwright-report and artifacts..."
cd "$REPO_ROOT"
if [ -d doc_processor/playwright-report ]; then
  mkdir -p "$ART/playwright-report"
  cp -a doc_processor/playwright-report/* "$ART/playwright-report/" || true
fi
find doc_processor -type f \( -iname '*screenshot*.png' -o -iname '*.png' -o -iname '*.html' -o -iname '*.log' -o -iname '*.xml' \) -print | while read -r f; do
  mkdir -p "$ART/$(dirname "$f")"
  cp -a "$f" "$ART/$f" || true
done

TARBALL="$ART.tar.gz"
tar -C /tmp -czf "$TARBALL" "$(basename "$ART")" || true
echo "TARBALL=$TARBALL"
echo "Done"

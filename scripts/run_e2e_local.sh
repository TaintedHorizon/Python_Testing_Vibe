#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "[run_e2e_local] Repo root: $ROOT_DIR"

if [ ! -d "doc_processor/venv" ]; then
  echo "Creating venv at doc_processor/venv"
  python3 -m venv doc_processor/venv
fi
. doc_processor/venv/bin/activate

echo "Installing Python deps (may be no-op if already installed)"
pip install --upgrade pip
pip install -r doc_processor/requirements.txt
pip install playwright pytest-playwright pytest

echo "Installing Playwright browsers"
python -m playwright install --with-deps || true

export PLAYWRIGHT_E2E=1
export FAST_TEST_MODE=1
export SKIP_OLLAMA=1
export PYTHONPATH="$ROOT_DIR/doc_processor":${PYTHONPATH:-}

echo "Running pytest e2e tests"
pytest -q doc_processor/tests/e2e

echo "Done. Artifacts (if any) are under doc_processor/tests/e2e/artifacts"

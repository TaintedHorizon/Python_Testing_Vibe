#!/usr/bin/env bash
set -euo pipefail

# Lightweight wrapper to run the repo's run_local_e2e.sh with safe overrides.
# Usage: ./scripts/run_e2e_wrapper.sh [--dry-run]

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1
fi

SAFE_DB="$ROOT_DIR/doc_processor/documents_e2e.db"
SAFE_BACKUP_DIR="$ROOT_DIR/doc_processor/test_backups"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "DRY RUN: Would run with: DATABASE_PATH=$SAFE_DB DB_BACKUP_DIR=$SAFE_BACKUP_DIR FAST_TEST_MODE=1 SKIP_OLLAMA=1 PLAYWRIGHT_E2E=1 ./scripts/run_local_e2e.sh"
  exit 0
fi

echo "Running E2E wrapper: using safe DB path: $SAFE_DB"
DATABASE_PATH="$SAFE_DB" \
DB_BACKUP_DIR="$SAFE_BACKUP_DIR" \
FAST_TEST_MODE=1 SKIP_OLLAMA=1 PLAYWRIGHT_E2E=1 ./scripts/run_local_e2e.sh

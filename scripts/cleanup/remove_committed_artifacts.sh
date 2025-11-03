#!/usr/bin/env bash
# Interactive helper to untrack committed CI/test artifact directories without deleting local copies.
# Usage: ./scripts/cleanup/remove_committed_artifacts.sh

set -euo pipefail

echo "This script will run 'git rm --cached' on candidate directories and add entries to .gitignore."
read -p "Proceed? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Aborted. No changes made."
  exit 0
fi

CANDIDATES=(
  "doc_processor/ci_logs"
  "doc_processor/tests/e2e/artifacts"
)

for d in "${CANDIDATES[@]}"; do
  if [ -d "$d" ]; then
    echo "Untracking files under $d"
    git rm --cached -r "$d" || true
  else
    echo "Directory $d not present; skipping"
  fi
done

# Ensure .gitignore already contains entries (we added them earlier).
if ! git diff --name-only --cached | grep -q "^\.gitignore"; then
  git add .gitignore || true
fi

echo "Commit the changes with:"
echo "  git commit -m 'chore: remove committed CI/test artifacts and ignore artifact dirs'"
echo "Then push: git push origin <branch>"

echo "Note: If any secrets were exposed, rotate them immediately. See docs/security-cleanup.md for guidance."

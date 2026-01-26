#!/usr/bin/env bash
# Prevent accidental commits of generated artifacts used by CI and tests.
# To enable: run `ln -s ../../hooks/prevent_artifact_commit.sh .git/hooks/pre-commit`

set -euo pipefail

staged=$(git diff --cached --name-only --no-renames || true)
if [ -z "$staged" ]; then
  exit 0
fi

blocked_regex='^(ci_logs/|doc_processor/tests/e2e/artifacts/)'
blocked_files=""

while IFS= read -r f; do
  if echo "$f" | grep -Eq "$blocked_regex"; then
    blocked_files+="$f\n"
  fi
done <<< "$staged"

if [ -n "$blocked_files" ]; then
  echo "ERROR: You are attempting to commit generated artifacts."
  echo "This repository tracks no CI/test artifacts. Remove them from the commit or add rules to .gitignore."
  echo
  echo "Offending files:" && echo -e "$blocked_files"
  echo
  echo "To enable this check for your local repo run:" 
  echo "  ln -s ../../hooks/prevent_artifact_commit.sh .git/hooks/pre-commit"
  exit 1
fi

exit 0

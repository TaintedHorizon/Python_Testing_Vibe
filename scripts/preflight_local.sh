#!/usr/bin/env bash
set -euo pipefail

# Local preflight script to run before opening PRs.
# Usage: ./scripts/preflight_local.sh

echo "Running local preflight checks..."

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$ROOT"

echo "1) Quick Python syntax check (all tracked .py files)"
git ls-files '*.py' | xargs -r -n 50 python -m py_compile || {
  echo "ERROR: Python syntax errors detected. Fix before opening a PR." >&2
  exit 1
}

echo "2) Critical flake8 checks (E9,F63,F7,F82) in doc_processor"
if ! command -v flake8 >/dev/null 2>&1; then
  echo "flake8 not found — install it to run lint checks: pip install flake8" >&2
else
  find doc_processor -name "*.py" \
    -not -path "*/venv/*" \
    -not -path "*/archive/*" \
    -not -name "*_backup.py" \
    -print0 | xargs -0 --no-run-if-empty flake8 --select=E9,F63,F7,F82 --show-source --statistics || {
    echo "ERROR: Critical flake8 issues detected. Fix before opening a PR." >&2
    exit 1
  }
fi

echo "3) Check for accidental root-level added files (compares to origin/main if available)"
if git rev-parse --verify origin/main >/dev/null 2>&1; then
  BASE_SHA=$(git rev-parse origin/main)
  HEAD_SHA=$(git rev-parse HEAD)
  mapfile -t added < <(git diff --name-only --diff-filter=A "$BASE_SHA" "$HEAD_SHA")
  allowed=("README.md" "Makefile" ".gitignore" ".github" "docs" "scripts" "dev_tools" "start_app.sh" "pyrightconfig.json" "pytest.ini" "Python_Testing_Vibe.code-workspace" "archive" "tools" "ui_tests" "LICENSE" ".venv-ci" ".ruff_cache")
  bad=()
  for f in "${added[@]}"; do
    if [[ -z "$f" ]]; then
      continue
    fi
    if [[ "$f" == */* ]]; then
      continue
    fi
    ok=0
    for a in "${allowed[@]}"; do
      if [[ "$f" == "$a" ]]; then
        ok=1
        break
      fi
    done
    if [[ $ok -eq 0 ]]; then
      bad+=("$f")
    fi
  done
  if (( ${#bad[@]} > 0 )); then
    echo "ERROR: Found root-level files added in this branch: ${bad[*]}" >&2
    echo "Move them into an appropriate subfolder (for example: .github/logs/) or update the PR." >&2
    exit 1
  fi
else
  echo "origin/main not available locally; skipping root-file added check (fetch origin to enable)."
fi

echo "4) Run repo preflight validator if available"
if [[ -f tools/pr_preflight_validate.py ]]; then
  if command -v python3 >/dev/null 2>&1; then
    python3 tools/pr_preflight_validate.py --repo "$(git config --get remote.origin.url || echo UNKNOWN)" || {
      echo "ERROR: preflight validator failed. Fix issues reported by tools/pr_preflight_validate.py" >&2
      exit 1
    }
  else
    echo "python3 not found; skipping preflight validator (install Python 3.11+)."
  fi
else
  echo "No tools/pr_preflight_validate.py found; skipping preflight validator."
fi

echo "Preflight checks passed (or non-fatal checks skipped). You can proceed to open the PR."

exit 0

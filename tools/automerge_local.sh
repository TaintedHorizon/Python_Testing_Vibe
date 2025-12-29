#!/usr/bin/env bash
set -euo pipefail

# tools/automerge_local.sh
# Lightweight helper to add the 'automerge' label and request auto-merge
# using the local `gh` (GitHub CLI) auth of whoever runs the script.
# This avoids changing workflows on GitHub and runs with your user permissions.

usage() {
  cat <<EOF
Usage: $0 <pr-number>

Prerequisites:
  - Install GitHub CLI (`gh`) and authenticate: `gh auth login`.
  - Your account must have permission to add labels and merge the PR.

What it does:
  1) Adds the 'automerge' label to the PR (creates the label if missing).
  2) Attempts to enable auto-merge (if supported by the server/CLI) or
     triggers an immediate merge when checks already passed.

Examples:
  $0 88

EOF
}

if [[ ${#} -ne 1 ]]; then
  usage
  exit 2
fi

PR=$1
OWNER_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
if [[ -z "$OWNER_REPO" ]]; then
  echo "Unable to determine repository via gh. Run 'gh auth status' and 'gh repo view'." >&2
  exit 2
fi

echo "Repository: $OWNER_REPO"

# 1) Ensure label exists (create if necessary)
if gh label view automerge >/dev/null 2>&1; then
  echo "Label 'automerge' exists."
else
  echo "Creating label 'automerge'..."
  gh label create automerge --color ededed --description "Auto-merge when smoke CI passes" || true
fi

# 2) Add label to PR
echo "Adding label 'automerge' to PR #$PR"
gh pr edit "$PR" --add-label automerge

# 3) Try to enable auto-merge (gh supports --auto for merge)
# If the server/branch protection supports auto-merge, this will schedule merging.
# Otherwise, attempt immediate merge if checks already passed.

echo "Attempting to auto-merge PR #$PR (this will wait for checks if supported)..."
if gh pr merge "$PR" --auto --merge --body "Auto-merged by local helper" >/dev/null 2>&1; then
  echo "Auto-merge scheduled or completed for PR #$PR."
  exit 0
fi

# Fallback: if auto didn't schedule, check if all checks passed and merge now
echo "Auto-merge not scheduled. Checking check-run statuses..."
CHECKS_OK=$(gh pr checks "$PR" --json checkSuites -q '.[] | select(.conclusion=="SUCCESS")' || true)
if [[ -n "$CHECKS_OK" ]]; then
  echo "Checks appear to have successes; attempting immediate merge..."
  gh pr merge "$PR" --merge --body "Auto-merged by local helper" || {
    echo "Immediate merge failed. You may need to merge manually or adjust protections." >&2
    exit 1
  }
  echo "PR #$PR merged.";
  exit 0
fi

echo "Checks are not yet passing or auto-merge not supported. The label has been added; the PR will be ready for merge once CI passes.";
exit 0

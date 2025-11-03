#!/usr/bin/env bash
set -euo pipefail

# Safely add a required status check context to branch protection for a branch.
# Usage:
#   .github/scripts/add_required_check.sh --repo owner/repo --branch main --context validate-workflows
# Requires: gh CLI authenticated and jq installed. Caller must have admin permissions on the repo.

REPO_DEFAULT="TaintedHorizon/Python_Testing_Vibe"
BRANCH_DEFAULT="main"
CONTEXT_DEFAULT="validate-workflows"

usage(){
  cat <<EOF
Usage: $0 [--repo owner/repo] [--branch branch] [--context context-name]

Adds the given context to the branch protection required status checks for the branch.
If branch protection does not exist, it will create a minimal protection payload that
requires the context.

Example:
  $0 --repo TaintedHorizon/Python_Testing_Vibe --branch main --context validate-workflows
EOF
}

REPO="$REPO_DEFAULT"
BRANCH="$BRANCH_DEFAULT"
CONTEXT="$CONTEXT_DEFAULT"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2;;
    --branch) BRANCH="$2"; shift 2;;
    --context) CONTEXT="$2"; shift 2;;
    --help|-h) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI required. Install from https://cli.github.com/" >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq required. Install jq." >&2
  exit 2
fi

echo "Repo: $REPO"
echo "Branch: $BRANCH"
echo "Context to add: $CONTEXT"

set -x

# Try to get current protection; if 404 or missing, gh api will exit non-zero
prot_json=""
if prot_json=$(gh api /repos/${REPO}/branches/${BRANCH}/protection 2>/dev/null); then
  echo "Existing branch protection fetched"
  # Ensure the required_status_checks object exists and add the context if missing
  updated=$(printf '%s' "$prot_json" | jq --arg ctx "$CONTEXT" '
    .required_status_checks = (.required_status_checks // {"strict": true, "contexts": []}) |
    .required_status_checks.contexts |= (if index($ctx) then . else . + [$ctx] end)
  ')
else
  echo "No branch protection found, creating minimal protection with required context"
  updated=$(jq -n --arg ctx "$CONTEXT" '{ required_status_checks: { strict: true, contexts: [$ctx] }, enforce_admins: false, required_pull_request_reviews: null, restrictions: null }')
fi

tmp=$(mktemp)
printf '%s' "$updated" > "$tmp"

echo "Applying branch protection (this will replace the branch protection payload)"
gh api --method PUT /repos/${REPO}/branches/${BRANCH}/protection --input "$tmp"

rm -f "$tmp"

echo "Done. Branch protection updated."

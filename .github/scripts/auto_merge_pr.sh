#!/usr/bin/env bash
set -euo pipefail
# Auto-merge a PR after a quiet window and successful checks.
# Usage: auto_merge_pr.sh <owner> <repo> <pr_number> [wait_seconds] [check_interval]
# Example: auto_merge_pr.sh TaintedHorizon Python_Testing_Vibe 51 86400 300

OWNER="$1"
REPO="$2"
PR="$3"
WAIT_SECONDS="${4:-86400}"
CHECK_INTERVAL="${5:-300}"
TOKEN="${GITHUB_TOKEN:-}"

if [ -z "$TOKEN" ]; then
  echo "GITHUB_TOKEN not set. Set GITHUB_TOKEN in the environment and re-run to enable auto-merge."
  exit 1
fi

echo "$(date): auto-merge monitor starting for ${OWNER}/${REPO} PR #${PR}"
echo "Waiting ${WAIT_SECONDS} seconds (quiet window) before attempting merge when checks are green..."
sleep "$WAIT_SECONDS"

while true; do
  # Get PR head sha
  COMMIT_SHA=$(curl -s -H "Authorization: token ${TOKEN}" "https://api.github.com/repos/${OWNER}/${REPO}/pulls/${PR}" | jq -r '.head.sha')
  if [ -z "$COMMIT_SHA" ] || [ "$COMMIT_SHA" = "null" ]; then
    echo "$(date): failed to read PR head sha; retrying in ${CHECK_INTERVAL}s"
    sleep "$CHECK_INTERVAL"
    continue
  fi

  # Check combined status for the commit
  STATE=$(curl -s -H "Authorization: token ${TOKEN}" "https://api.github.com/repos/${OWNER}/${REPO}/commits/${COMMIT_SHA}/status" | jq -r '.state')

  echo "$(date): commit ${COMMIT_SHA} checks state: ${STATE}"
  if [ "$STATE" = "success" ]; then
    echo "$(date): checks green — attempting merge"
    MERGE_RESPONSE=$(curl -s -X PUT -H "Authorization: token ${TOKEN}" -d '{"merge_method":"squash"}' "https://api.github.com/repos/${OWNER}/${REPO}/pulls/${PR}/merge")
    echo "Merge response: ${MERGE_RESPONSE}"
    exit 0
  fi

  echo "$(date): checks not green yet — sleeping ${CHECK_INTERVAL}s"
  sleep "$CHECK_INTERVAL"
done

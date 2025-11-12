#!/usr/bin/env bash
set -euo pipefail

PR=68
OWNER="TaintedHorizon"
REPO="Python_Testing_Vibe"
LOG=/tmp/pr-watch-68.log
MAX_CHECKS=240   # 240 checks * 30s = 2 hours max
SLEEP=30
i=0

echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") Starting PR watch for #$PR" >"$LOG"

while [ $i -lt $MAX_CHECKS ]; do
  i=$((i+1))
  info=$(gh pr view "$PR" --repo "$OWNER/$REPO" --json number,state,merged,mergeable,mergeStateStatus --jq '{number: .number, state: .state, merged: .merged, mergeable: .mergeable, mergeState: .mergeStateStatus}') || true
  merged=$(echo "$info" | jq -r '.merged // "false"')
  state=$(echo "$info" | jq -r '.state // ""')
  mergeable=$(echo "$info" | jq -r '.mergeable // ""')
  mergeState=$(echo "$info" | jq -r '.mergeState // ""')
  echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") check $i: state=$state merged=$merged mergeable=$mergeable mergeState=$mergeState" >>"$LOG"

  if [ "$merged" = "true" ] || [ "$state" = "merged" ]; then
    echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") PR #$PR merged. Exiting." >>"$LOG"
    exit 0
  fi

  sleep $SLEEP
done

echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") Timeout waiting for PR #$PR after $MAX_CHECKS checks." >>"$LOG"
exit 2

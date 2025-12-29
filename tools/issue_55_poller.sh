#!/usr/bin/env bash
set -euo pipefail
# Poll GitHub and the auto-close watcher log every 30 minutes and append a status line
REPO="TaintedHorizon/Python_Testing_Vibe"
LOG=".auto_close_issue_55.status.log"
WATCHER_LOG=".auto_close_issue_55.log"
PR_NUMBER=86
INTERVAL=${INTERVAL_SECONDS:-1800}

echo "Starting issue_55 poller (interval ${INTERVAL}s)" >> "$LOG"
while true; do
  TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  ISSUE_STATE=$(gh issue view 55 --repo "$REPO" --json state --jq '.state' 2>/dev/null || echo "UNKNOWN")
  PR_MERGE_COMMIT=$(gh pr view "$PR_NUMBER" --repo "$REPO" --json mergeCommit --jq '.mergeCommit.oid' 2>/dev/null || echo "")
  if [ -n "$PR_MERGE_COMMIT" ]; then
    COMBINED=$(gh api repos/TaintedHorizon/Python_Testing_Vibe/commits/$PR_MERGE_COMMIT/status --jq '{state: .state, total_count: .total_count}' 2>/dev/null || echo '{}')
    SUITES=$(gh api repos/TaintedHorizon/Python_Testing_Vibe/commits/$PR_MERGE_COMMIT/check-suites --jq '.check_suites | map({id: .id, status: .status, conclusion: .conclusion, app: .app.name})' 2>/dev/null || echo '[]')
  else
    COMBINED='{}'
    SUITES='[]'
  fi

  echo "[$TS] issue=$ISSUE_STATE commit=${PR_MERGE_COMMIT:-none} combined=${COMBINED} check_suites=${SUITES}" >> "$LOG"

  # capture last 40 lines of watcher log for quick context
  if [ -f "$WATCHER_LOG" ]; then
    echo "--- watcher tail @ $TS ---" >> "$LOG"
    tail -n 40 "$WATCHER_LOG" >> "$LOG" 2>/dev/null || true
  fi

  sleep "$INTERVAL"
done

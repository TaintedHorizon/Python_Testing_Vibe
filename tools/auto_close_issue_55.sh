#!/usr/bin/env bash
set -u

# Auto-close Issue #55 when CI for `main` goes green.
# Usage: tools/auto_close_issue_55.sh [interval_seconds] [timeout_seconds]

OWNER="TaintedHorizon"
REPO="Python_Testing_Vibe"
ISSUE=55
REF="main"
INTERVAL=${1:-120}   # 2 minutes
TIMEOUT=${2:-21600}  # 6 hours

# Use .github directories for operational logs/pids by default
LOG_DIR=${LOG_DIR:-.github/logs}
SCRIPTS_DIR=${SCRIPTS_DIR:-.github/scripts}
mkdir -p "$LOG_DIR" "$SCRIPTS_DIR"

LOG="$LOG_DIR/auto_close_issue_55.log"
PIDFILE="$SCRIPTS_DIR/auto_close_issue_55.pid"

echo "$(date -u) | Starting auto-close watcher for issue #${ISSUE} (poll ${INTERVAL}s, timeout ${TIMEOUT}s)" >> "$LOG"
START_TS=$(date +%s)
END_TS=$((START_TS + TIMEOUT))

# Resolve commit SHA for the branch/ref we care about
SHA=$(gh api "/repos/${OWNER}/${REPO}/commits/${REF}" -q .sha 2>/dev/null || true)
if [[ -z "$SHA" ]]; then
  echo "$(date -u) | ERROR: could not resolve commit for ${REF}" >> "$LOG"
  exit 2
fi

echo "$(date -u) | Monitoring commit $SHA" >> "$LOG"

# write pidfile and ensure cleanup
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT INT TERM

while [[ $(date +%s) -le $END_TS ]]; do
  echo "$(date -u) | Checking check-suites for ${SHA}..." >> "$LOG"
  SUITES_JSON=$(gh api "/repos/${OWNER}/${REPO}/commits/${SHA}/check-suites" 2>/dev/null || echo '{}')
  TOTAL=$(echo "$SUITES_JSON" | jq '.check_suites | length')
  INCOMPLETE=$(echo "$SUITES_JSON" | jq '[.check_suites[] | select(.status != "completed")] | length')
  FAILURES=$(echo "$SUITES_JSON" | jq '[.check_suites[] | select(.status == "completed" and .conclusion != "success")] | length')
  echo "$(date -u) | check-suites total=${TOTAL} incomplete=${INCOMPLETE} failures=${FAILURES}" >> "$LOG"

  if [[ "$TOTAL" -eq 0 ]]; then
    echo "$(date -u) | No check-suites found for ${SHA} (treating as pending)" >> "$LOG"
  elif [[ "$INCOMPLETE" -gt 0 ]]; then
    echo "$(date -u) | Some check-suites are still running (pending)" >> "$LOG"
  elif [[ "$FAILURES" -gt 0 ]]; then
    echo "$(date -u) | Detected failing check-suites for ${SHA}. Posting status comment and exiting." >> "$LOG"
    gh issue comment $ISSUE --body "Auto-close watcher detected failing checks for commit ${SHA}. Not closing the issue. See workflow runs: https://github.com/${OWNER}/${REPO}/actions?query=sha:${SHA}" >> "$LOG" 2>&1 || true
    exit 3
  else
    echo "$(date -u) | All check-suites completed successfully — posting comment and closing issue #${ISSUE}" >> "$LOG"
    gh issue comment $ISSUE --body "Auto-close watcher: all required checks for commit ${SHA} passed. Closing Issue #${ISSUE} as requested." >> "$LOG" 2>&1 || true
    gh api -X PATCH "/repos/${OWNER}/${REPO}/issues/${ISSUE}" -f state=closed >> "$LOG" 2>&1 || true
    echo "$(date -u) | Issue #${ISSUE} closed." >> "$LOG"
    exit 0
  fi

  echo "$(date -u) | State is '${STATE}', sleeping ${INTERVAL}s..." >> "$LOG"
  sleep $INTERVAL
done

echo "$(date -u) | Timeout reached waiting for checks on commit ${SHA}. Posting timeout comment." >> "$LOG"
gh issue comment $ISSUE --body "Auto-close watcher timed out after ${TIMEOUT}s waiting for checks on commit ${SHA}. Please review: https://github.com/${OWNER}/${REPO}/actions?query=sha:${SHA}" >> "$LOG" 2>&1 || true
echo "$(date -u) | Exiting due to timeout." >> "$LOG"
exit 4

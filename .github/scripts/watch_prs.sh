#!/usr/bin/env bash
set -euo pipefail

REPO="TaintedHorizon/Python_Testing_Vibe"
LOG_DIR=".github/logs"
LOG_FILE="$LOG_DIR/pr_watch.log"
PID_FILE=".github/scripts/watch_prs.pid"
PRS=(52 53 54)

mkdir -p "$LOG_DIR"
echo "Starting PR watcher at $(date --iso-8601=seconds)" >> "$LOG_FILE"
echo $$ > "$PID_FILE"

last_states=""

while true; do
  now=$(date --iso-8601=seconds)
  echo "[$now] Checking PRs: ${PRS[*]}" >> "$LOG_FILE"
  all_merged=true
  state_line=""
  for pr in "${PRS[@]}"; do
    # Query PR status
  # Use tostring for numeric/boolean fields to avoid jq type errors on concatenation
  out=$(gh pr view "$pr" --repo "$REPO" --json number,state,mergedAt,mergeable,mergeStateStatus --jq '(.number|tostring) + "|" + .state + "|" + (.mergedAt // "null") + "|" + ((.mergeable) | tostring // "UNKNOWN") + "|" + ((.mergeStateStatus) | tostring // "UNKNOWN")' 2>/dev/null || true)
    if [ -z "$out" ]; then
      echo "[$now] PR $pr: (failed to query)" >> "$LOG_FILE"
      all_merged=false
      state_line+="$pr:ERROR;"
      continue
    fi
    echo "[$now] PR $pr: $out" >> "$LOG_FILE"
    state_line+="$out;"
    merged=$(echo "$out" | cut -d'|' -f3)
    if [ "$merged" = "null" ]; then
      all_merged=false
    fi
  done

  if [ "$state_line" != "$last_states" ]; then
    echo "[$now] State change: $state_line" >> "$LOG_FILE"
    last_states="$state_line"
  fi

  if [ "$all_merged" = true ]; then
    echo "[$now] All watched PRs merged — exiting watcher." >> "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 0
  fi

  sleep 30
done

#!/usr/bin/env bash
set -euo pipefail
PR=52
REPO="TaintedHorizon/Python_Testing_Vibe"
LOG=".github/logs/auto_merge_52.log"
PIDFILE=".github/scripts/auto_merge_52.pid"

mkdir -p "$(dirname "$LOG")"

echo "Starting auto-merge poller for PR $PR at $(date --iso-8601=seconds)" >> "$LOG"

echo $$ > "$PIDFILE"

while true; do
  now=$(date --iso-8601=seconds)
  echo "[$now] Checking PR $PR" >> "$LOG"
  # Query mergeable state via API
  resp=$(gh api repos/$REPO/pulls/$PR --jq '.mergeable, .mergeable_state' 2>/dev/null || true)
  if [ -z "$resp" ]; then
    echo "[$now] gh api call failed or returned empty" >> "$LOG"
    sleep 30
    continue
  fi
  # resp prints lines like: true\nblocked
  mergeable=$(echo "$resp" | sed -n '1p')
  merge_state=$(echo "$resp" | sed -n '2p')
  echo "[$now] mergeable=$mergeable merge_state=$merge_state" >> "$LOG"

  if [[ "$mergeable" == "true" && "$merge_state" == "clean" ]]; then
    echo "[$now] Conditions met: attempting merge" >> "$LOG"
    if gh pr merge "$PR" --repo "$REPO" --squash --delete-branch --body "chore(archive): move manual-smoke.yml to .github/workflows/archive/ (docs-first)" >> "$LOG" 2>&1; then
      echo "[$now] Merge succeeded" >> "$LOG"
      exit 0
    else
      echo "[$now] Merge attempt failed; will retry" >> "$LOG"
    fi
  else
    echo "[$now] Not mergeable yet (mergeable=$mergeable merge_state=$merge_state)" >> "$LOG"
  fi
  sleep 30
done

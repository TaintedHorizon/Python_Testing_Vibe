#!/usr/bin/env bash
set -euo pipefail
PR=76
REPO="TaintedHorizon/Python_Testing_Vibe"
MAX_SECONDS=1200  # 20 minutes
INTERVAL=15
START=$SECONDS
printf "Watching PR #%s in %s for up to %d seconds (poll every %d s)\n" "$PR" "$REPO" "$MAX_SECONDS" "$INTERVAL"
while [ $((SECONDS - START)) -lt "$MAX_SECONDS" ]; do
  state_json=$(gh pr view "$PR" --repo "$REPO" --json merged,mergeStateStatus 2>/dev/null || echo '{}')
  merged=$(echo "$state_json" | grep -Po '"merged"\s*:\s*\K(true|false)' || true)
  mergeState=$(echo "$state_json" | grep -Po '"mergeStateStatus"\s*:\s*"\K[^"]+' || true)
  printf "[%s] merged=%s state=%s\n" "$(date -u +'%Y-%m-%d %H:%M:%S UTC')" "${merged:-false}" "${mergeState:-UNKNOWN}"
  gh pr checks "$PR" --repo "$REPO" || true
  if [ "${merged:-false}" = "true" ]; then
    printf "PR merged!\n"
    gh pr view "$PR" --repo "$REPO" --json number,title,url,mergedAt --jq '. | {number, title, url, mergedAt}'
    exit 0
  fi
  sleep "$INTERVAL"
done
printf "Timeout reached without merge.\n"
exit 2

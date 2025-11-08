#!/usr/bin/env bash
set -euo pipefail

# Monitor recent `validate-workflows` runs and fetch logs for failures.
# Usage: ./monitor_validate_runs.sh [--repo owner/repo] [--interval-seconds N] [--iterations N]
# Default: repo=TaintedHorizon/Python_Testing_Vibe, interval=43200 (12h), iterations=4 (48h)

REPO_DEFAULT="TaintedHorizon/Python_Testing_Vibe"
INTERVAL=43200
ITERATIONS=4

usage(){
  cat <<EOF
Usage: $0 [--repo owner/repo] [--interval-seconds N] [--iterations N]
Polls the most recent validate-workflows runs every interval and saves logs for failed runs.
Requires: gh CLI and jq installed and authenticated.

Example:
  $0 --repo TaintedHorizon/Python_Testing_Vibe --interval-seconds 3600 --iterations 24
EOF
}

REPO="$REPO_DEFAULT"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2;;
    --interval-seconds) INTERVAL="$2"; shift 2;;
    --iterations) ITERATIONS="$2"; shift 2;;
    --help|-h) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found" >&2; exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq not found" >&2; exit 2
fi

LOG_DIR=".github/logs"
SEEN_FILE=".github/scripts/monitor_seen.txt"
mkdir -p "$LOG_DIR"
touch "$SEEN_FILE"

echo "Starting monitor for workflow 'validate-workflows' in repo ${REPO}"
echo "Interval: ${INTERVAL}s, iterations: ${ITERATIONS} (total ~$((${INTERVAL}*${ITERATIONS}))s)"

iter=0
while [ $iter -lt "$ITERATIONS" ]; do
  echo "[monitor] iteration $((iter+1)) of ${ITERATIONS} - $(date -u)"

  # List recent runs as JSON. Use GH CLI --json; fall back to text parsing if not supported.
  runs_json=$(gh run list --workflow validate-workflows.yml -R "$REPO" --limit 50 --json id,status,conclusion,headBranch 2>/dev/null || true)

  if [ -n "$runs_json" ] && [ "$runs_json" != "null" ]; then
    # Find completed runs where conclusion != success
    failed_ids=$(echo "$runs_json" | jq -r '.[] | select(.status=="completed" and (.conclusion != "success" and .conclusion != "neutral")) | .id') || true
  else
    # If --json unsupported, use text list and try to extract IDs (best-effort)
    echo "gh run list did not return JSON; attempting text parse" >&2
    failed_ids="$(gh run list --workflow validate-workflows.yml -R "$REPO" --limit 50 2>/dev/null | awk '/ X / || / failed / {print $1}' || true)"
  fi

  for id in $failed_ids; do
    # Skip if we've already processed this run
    if grep -q "^${id}$" "$SEEN_FILE" 2>/dev/null; then
      continue
    fi
    echo "[monitor] Found failed run: $id - fetching logs"
    outfile="$LOG_DIR/validate_run_${id}.log"
    gh run view "$id" --repo "$REPO" --log > "$outfile" 2>&1 || true
    echo "$(date -u) - run ${id} - saved logs to ${outfile}" >> "$LOG_DIR/summary.txt"
    echo "$id" >> "$SEEN_FILE"
  done

  echo "[monitor] sleeping ${INTERVAL}s"
  sleep "$INTERVAL"
  iter=$((iter+1))
done

echo "Monitor finished. Logs (if any) are under ${LOG_DIR}. Summary: ${LOG_DIR}/summary.txt"

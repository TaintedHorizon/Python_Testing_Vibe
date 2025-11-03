#!/usr/bin/env bash
set -euo pipefail

# Poll a GitHub Actions run until it completes, then print status and optionally fetch logs on failure.
# Usage:
#   ./poll_run.sh <run-id> [--repo owner/repo] [--interval 10] [--retries 60]
# Examples:
#   ./poll_run.sh 19042679649 --repo TaintedHorizon/Python_Testing_Vibe

REPO_DEFAULT="TaintedHorizon/Python_Testing_Vibe"
INTERVAL=10
RETRIES=60

usage() {
  cat <<EOF
Usage: $0 <run-id> [--repo owner/repo] [--interval N] [--retries N]
Polls a GitHub Actions run until it reaches a completed state. Requires the GH CLI and jq.

Environment: Ensure GH CLI is authenticated (gh auth login) and jq is installed.

Examples:
  $0 19042679649 --repo TaintedHorizon/Python_Testing_Vibe
EOF
}

if [ "$#" -lt 1 ]; then
  usage
  exit 2
fi

RUN_ID=""
REPO="$REPO_DEFAULT"

RUN_ID="$1"
shift || true

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      REPO="$2"; shift 2;;
    --interval)
      INTERVAL="$2"; shift 2;;
    --retries)
      RETRIES="$2"; shift 2;;
    --help|-h)
      usage; exit 0;;
    *)
      echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install from https://cli.github.com/" >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq not found. Install jq to parse JSON outputs." >&2
  exit 2
fi

echo "Polling run ${RUN_ID} in repo ${REPO} (interval=${INTERVAL}s, retries=${RETRIES})"

count=0
while [ $count -lt "$RETRIES" ]; do
  # Get status and conclusion using the GH CLI JSON output
  json=$(gh run view "$RUN_ID" --repo "$REPO" --json status,conclusion --jq '.') || true
  # json may be empty if the run id isn't found; handle gracefully
  if [ -z "$json" ] || [ "$json" = "null" ]; then
    echo "Run ${RUN_ID} not found (attempt $((count+1))/${RETRIES}). Retrying in ${INTERVAL}s..."
    sleep "$INTERVAL"
    count=$((count+1))
    continue
  fi

  status=$(echo "$json" | jq -r '.status // empty') || status=""
  conclusion=$(echo "$json" | jq -r '.conclusion // empty') || conclusion=""

  echo "[attempt $((count+1))] status=${status} conclusion=${conclusion}"

  if [ "$status" = "completed" ]; then
    echo "Run ${RUN_ID} completed with conclusion: ${conclusion}"
    if [ "$conclusion" = "success" ] || [ "$conclusion" = "neutral" ]; then
      exit 0
    else
      echo "Fetching full run logs for debugging..."
      gh run view "$RUN_ID" --repo "$REPO" --log || true
      exit 1
    fi
  fi

  sleep "$INTERVAL"
  count=$((count+1))
done

echo "Timed out waiting for run ${RUN_ID} after ${RETRIES} attempts." >&2
exit 2

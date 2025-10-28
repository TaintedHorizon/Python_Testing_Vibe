#!/usr/bin/env bash
# Fetch the latest completed 'heavy-deps' workflow run's wheelhouse artifact.
# Usage:
#   ./scripts/ci/fetch_wheelhouse_poll.sh \
#       --repo OWNER/REPO \
#       [--workflow heavy-deps.yml] \
#       [--artifact wheelhouse-3.11] \
#       [--outdir ci_artifacts] \
#       [--timeout-min 10] [--interval-sec 15]

set -euo pipefail

REPO="TaintedHorizon/Python_Testing_Vibe"
WORKFLOW="heavy-deps.yml"
ARTIFACT_NAME="wheelhouse-3.11"
OUTDIR="ci_artifacts"
TIMEOUT_MIN=10
INTERVAL_SEC=15

print_usage() {
  sed -n '1,200p' <<'USAGE'
Usage: fetch_wheelhouse_poll.sh [options]

Options:
  --repo OWNER/REPO       GitHub repo (default: TaintedHorizon/Python_Testing_Vibe)
  --workflow PATH         Workflow filename (default: heavy-deps.yml)
  --artifact NAME         Artifact name to download (default: wheelhouse-3.11)
  --outdir DIR            Output base directory (default: ci_artifacts)
  --timeout-min N         Max minutes to wait for completion (default: 10)
  --interval-sec N        Poll interval in seconds (default: 15)
  -h, --help              Show this help
USAGE
}

while [[ ${#} -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2;;
    --workflow) WORKFLOW="$2"; shift 2;;
    --artifact) ARTIFACT_NAME="$2"; shift 2;;
    --outdir) OUTDIR="$2"; shift 2;;
    --timeout-min) TIMEOUT_MIN="$2"; shift 2;;
    --interval-sec) INTERVAL_SEC="$2"; shift 2;;
    -h|--help) print_usage; exit 0;;
    *) echo "Unknown arg: $1"; print_usage; exit 2;;
  esac
done

mkdir -p "$OUTDIR"

echo "Repo: $REPO"
echo "Workflow: $WORKFLOW"
echo "Artifact: $ARTIFACT_NAME"
echo "Outdir: $OUTDIR"
echo "Timeout: ${TIMEOUT_MIN}m, Interval: ${INTERVAL_SEC}s"

# find latest run ID for the workflow using JSON output (more robust than plain text parsing)
# We use the run "databaseId" which is a stable numeric id accepted by gh run view/download
RUN_NUMBER=$(gh run list --repo "$REPO" --workflow "$WORKFLOW" --limit 1 --json databaseId,status,conclusion --jq '.[0].databaseId' 2>/dev/null || true)
if [[ -z "$RUN_NUMBER" || "$RUN_NUMBER" == "null" ]]; then
  echo "No runs found for workflow $WORKFLOW in $REPO" >&2
  exit 3
fi
echo "Selected run: $RUN_NUMBER"

# poll until completed or timeout
START_TS=$(date +%s)
TIMEOUT_SEC=$((TIMEOUT_MIN * 60))
while true; do
  STATUS=$(gh run view "$RUN_NUMBER" --repo "$REPO" --json status,conclusion --jq '.status')
  CONCL=$(gh run view "$RUN_NUMBER" --repo "$REPO" --json status,conclusion --jq '(.conclusion // "null")')
  echo "[poll] run=$RUN_NUMBER status=$STATUS conclusion=$CONCL"
  if [[ "$STATUS" == "completed" ]]; then
    echo "Run completed (conclusion=$CONCL)"
    break
  fi
  NOW_TS=$(date +%s)
  ELAPSED=$((NOW_TS - START_TS))
  if (( ELAPSED >= TIMEOUT_SEC )); then
    echo "Timeout waiting for run $RUN_NUMBER to complete (waited ${TIMEOUT_MIN}m)" >&2
    exit 4
  fi
  sleep "$INTERVAL_SEC"
done

# download artifact
DEST="$OUTDIR/run-$RUN_NUMBER"
mkdir -p "$DEST"
echo "Downloading artifact '$ARTIFACT_NAME' to $DEST"
if ! gh run download "$RUN_NUMBER" --repo "$REPO" --name "$ARTIFACT_NAME" -D "$DEST"; then
  echo "Artifact download failed or artifact not found" >&2
  exit 5
fi

# find tarball
TARPATH=$(ls "$DEST"/*.tgz 2>/dev/null || true)
if [[ -z "$TARPATH" ]]; then
  echo "No .tgz artifact found in $DEST" >&2
  exit 6
fi

mkdir -p "$DEST/list" "$DEST/extracted"
echo "TARBALL: $TARPATH"
tar -tzf "$TARPATH" > "$DEST/list/tar_contents.txt"
tar -xzf "$TARPATH" -C "$DEST/extracted"
find "$DEST/extracted" -type f -name '*.whl' > "$DEST/list/whl_files.txt" || true
grep -Ei 'numpy|pytesseract|pillow|Pillow' "$DEST/list/whl_files.txt" > "$DEST/list/critical_wheels.txt" || true

echo "Wheels found:"
wc -l "$DEST/list/whl_files.txt" || true
echo "Critical wheels (if any):"
cat "$DEST/list/critical_wheels.txt" || true

echo "Manifests written to: $DEST/list/"
echo "Done."

exit 0

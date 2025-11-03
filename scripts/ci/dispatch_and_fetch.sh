#!/usr/bin/env bash
# Safe helper to dispatch a GitHub Actions workflow and fetch a specific artifact
# Designed to be interactive and avoid long blocking loops or huge terminal output.
# Usage: ./scripts/ci/dispatch_and_fetch.sh <owner/repo> <workflow-file> <ref> <artifact-name>
# Example: ./scripts/ci/dispatch_and_fetch.sh TaintedHorizon/Python_Testing_Vibe heavy-deps.yml main wheelhouse-3.11

set -u

REPO=${1:-}
WORKFLOW=${2:-}
REF=${3:-main}
ART_NAME=${4:-wheelhouse-3.11}
OUTDIR=${5:-/tmp/wheelhouse_run}

if [ -z "$REPO" ] || [ -z "$WORKFLOW" ]; then
  echo "Usage: $0 <owner/repo> <workflow-file> [ref] [artifact-name] [outdir]" >&2
  exit 2
fi

# Trap SIGINT so the script exits cleanly instead of leaving partial state
trap 'echo "Interrupted by user"; exit 130' INT

echo "Dispatching workflow '$WORKFLOW' on ref '$REF' for repo '$REPO'..."
if ! gh workflow run "$WORKFLOW" --repo "$REPO" --ref "$REF"; then
  echo "Failed to dispatch workflow. Check gh auth (gh auth status)." >&2
  exit 1
fi

# Give GitHub a moment to register the dispatch
sleep 3

# Try to find a recent run for the workflow. We ask for the latest runs (limit 10) and take the newest createdAt.
# Use fields that gh exposes: number and createdAt
RUN_NUMBER=""
for i in 1 2 3 4 5; do
  RUN_NUMBER=$(gh run list --repo "$REPO" --workflow "$WORKFLOW" --limit 10 --json number,createdAt,status,conclusion --jq 'sort_by(.createdAt)[-1].number' 2>/dev/null || true)
  if [ -n "$RUN_NUMBER" ] && [ "$RUN_NUMBER" != "null" ]; then
    echo "Found run number: $RUN_NUMBER"; break
  fi
  echo "Run not visible yet (attempt $i), retrying in 3s..."; sleep 3
done

if [ -z "$RUN_NUMBER" ] || [ "$RUN_NUMBER" = "null" ]; then
  echo "Could not determine run number. Please check 'gh run list --workflow=$WORKFLOW' manually." >&2
  exit 1
fi

# Poll the run status with a small bounded loop. We avoid printing full logs; use --web to open UI if preferred.
for j in 1 2 3 4 5 6 7 8 9 10; do
  STATUS=$(gh run view "$RUN_NUMBER" --repo "$REPO" --json status --jq '.status' 2>/dev/null || true)
  CONCL=$(gh run view "$RUN_NUMBER" --repo "$REPO" --json conclusion --jq '.conclusion' 2>/dev/null || true)
  echo "[poll $j] run=$RUN_NUMBER status=$STATUS conclusion=$CONCL"
  if [ "$STATUS" = "completed" ]; then
    echo "Run completed with conclusion=$CONCL"; break
  fi
  # Suggest opening web UI on the 3rd poll to watch logs instead of long terminal polling
  if [ "$j" -eq 3 ]; then
    echo "Tip: open the run in your browser to watch logs: gh run view $RUN_NUMBER --repo $REPO --web"
  fi
  sleep 6
done

STATUS=$(gh run view "$RUN_NUMBER" --repo "$REPO" --json status --jq '.status' 2>/dev/null || true)
if [ "$STATUS" != "completed" ]; then
  echo "Run did not complete in the short polling window. Use 'gh run view $RUN_NUMBER --repo $REPO --web' and try again later." >&2
  exit 2
fi

# Download artifact (one-shot). Keep downloads in OUTDIR and avoid printing large outputs.
mkdir -p "$OUTDIR"
echo "Downloading artifact '$ART_NAME' for run $RUN_NUMBER into $OUTDIR..."
if ! gh run download "$RUN_NUMBER" --repo "$REPO" --name "$ART_NAME" -D "$OUTDIR"; then
  echo "Artifact download failed or artifact not present for run $RUN_NUMBER" >&2
  ls -la "$OUTDIR" || true
  exit 3
fi

# Find tarball inside or zip
ZIP=$(find "$OUTDIR" -type f -name "$ART_NAME*.zip" | head -n1 || true)
TGZ=$(find "$OUTDIR" -type f -name "$ART_NAME.tgz" | head -n1 || true)

if [ -n "$ZIP" ]; then
  echo "Extracting zip to $OUTDIR/zip_extract (quiet)..."
  mkdir -p "$OUTDIR/zip_extract"
  unzip -q "$ZIP" -d "$OUTDIR/zip_extract" || true
  TGZ=$(find "$OUTDIR/zip_extract" -type f -name "$ART_NAME.tgz" | head -n1 || true)
fi

if [ -n "$TGZ" ]; then
  echo "Found tarball: $TGZ — listing wheel filenames into $OUTDIR/wheels.txt"
  mkdir -p "$OUTDIR/list"
  tar -tzf "$TGZ" | grep '\.whl' > "$OUTDIR/list/wheels.txt" || true
  WCOUNT=$(wc -l < "$OUTDIR/list/wheels.txt" 2>/dev/null || echo 0)
  echo "Found $WCOUNT .whl files. Showing up to first 30 entries:" 
  head -n 30 "$OUTDIR/list/wheels.txt" || true
else
  echo "No tarball found; looking for .whl files directly in $OUTDIR"
  find "$OUTDIR" -type f -name '*.whl' > "$OUTDIR/list/wheels.txt" || true
  WCOUNT=$(wc -l < "$OUTDIR/list/wheels.txt" 2>/dev/null || echo 0)
  echo "Found $WCOUNT .whl files in artifact download. Showing up to first 30 entries:"
  head -n 30 "$OUTDIR/list/wheels.txt" || true
fi

# Check for critical wheels
echo "Checking for critical wheels (numpy, pytesseract, Pillow):"
grep -E 'numpy-|pytesseract|Pillow' "$OUTDIR/list/wheels.txt" || echo "No critical wheels matched"

echo "Summary file: $OUTDIR/list/wheels.txt"

echo "Done. If you'd like to inspect logs, open: gh run view $RUN_NUMBER --repo $REPO --web"

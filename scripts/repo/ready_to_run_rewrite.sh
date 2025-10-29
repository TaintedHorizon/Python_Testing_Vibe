#!/usr/bin/env bash
set -euo pipefail

# ready_to_run_rewrite.sh
# Prepares and (optionally) runs a git-filter-repo rewrite that removes a specific historical file.
# This script is intentionally gated: it will only execute if --confirm is passed.
# Otherwise it prints the exact commands and exits.

TARGET_PATH="Document_Scanner_Ollama_outdated/model_cache/craft_mlt_25k.pth"
THRESHOLD_MB=50
MIRROR_DIR="repo-rewrite.git"

usage() {
  cat <<EOF
Usage: $0 [--confirm]

This script will:
  - clone a mirror of the current origin into $MIRROR_DIR
  - run git-filter-repo to remove history for $TARGET_PATH
  - or alternatively remove any blob > ${THRESHOLD_MB}M

It will NOT push to origin. To execute destructive operations you MUST pass --confirm.
EOF
}

CONFIRM=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirm) CONFIRM=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 2;;
  esac
done

if [ -d "$MIRROR_DIR" ]; then
  echo "Mirror directory $MIRROR_DIR already exists. Remove it before proceeding." >&2
  exit 2
fi

ORIG_URL=$(git remote get-url origin 2>/dev/null || echo "$(pwd)")

echo "Mirror cloning from: $ORIG_URL"
echo "This will produce a mirror in: $MIRROR_DIR"

echo
echo "Planned git-filter-repo command (targeted path removal):"
echo
echo "git filter-repo --path '$TARGET_PATH' --invert-paths"
echo
echo "Planned git-filter-repo command (size-based alternative):"
echo
echo "git filter-repo --strip-blobs-bigger-than ${THRESHOLD_MB}M"
echo
if [ "$CONFIRM" -ne 1 ]; then
  echo "Dry run only. To execute the rewrite, re-run with --confirm. This script will still clone the mirror when --confirm is passed."
  exit 0
fi

echo "Confirm flag present. Proceeding..."

echo "Cloning mirror..."
git clone --mirror "$ORIG_URL" "$MIRROR_DIR"
cd "$MIRROR_DIR"

echo "Running git-filter-repo to remove path: $TARGET_PATH"
# Actual command
git filter-repo --path "$TARGET_PATH" --invert-paths

echo "Rewrite complete. The rewritten mirror is available at: $(pwd)"
echo "Inspect locally by cloning file://$(pwd) into a verification directory and running tests. No pushes were performed." 
echo "If maintainers approve, push with:" 
echo "  git push --force --all origin" 
echo "  git push --force --tags origin" 

exit 0

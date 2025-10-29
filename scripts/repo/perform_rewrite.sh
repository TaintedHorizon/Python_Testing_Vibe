#!/usr/bin/env bash
set -euo pipefail

# Safe helper to prepare and optionally run a git-filter-repo history rewrite.
# IMPORTANT: This script is intentionally conservative and will NOT push to origin.
# It creates a mirror clone, runs git-filter-repo according to chosen mode, and
# leaves the rewritten mirror in repo-rewrite.git for manual inspection.

usage() {
  cat <<EOF
Usage: $0 [--mode size|paths] [--size-mb N] [--paths file-with-paths]

Modes:
  size   - remove any blob larger than --size-mb (default 50)
  paths  - remove specific paths listed in the provided file (one path per line)

This script will:
  - clone a mirror of the current repo to repo-rewrite.git
  - run git-filter-repo in the chosen mode
  - produce verification instructions

It will NOT push any rewritten refs to origin. Review the rewritten mirror at repo-rewrite.git
before performing any push.
EOF
}

MODE= size
SIZE_MB=50
PATHS_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"; shift 2;;
    --size-mb)
      SIZE_MB="$2"; shift 2;;
    --paths)
      PATHS_FILE="$2"; shift 2;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown arg: $1"; usage; exit 2;;
  esac
done

if [ -z "$MODE" ] || { [ "$MODE" = "paths" ] && [ -z "$PATHS_FILE" ]; }; then
  usage; exit 2
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git not found in PATH" >&2; exit 2
fi

if ! python -c 'import git' >/dev/null 2>&1; then
  # Not strictly necessary, but warn if git-filter-repo likely not installed
  echo "Note: git-filter-repo may not be installed. Install with: pip install --user git-filter-repo" >&2
fi

ORIG_URL=$(git remote get-url origin 2>/dev/null || echo "$(pwd)")
WORKDIR=$(pwd)

MIRROR_DIR="repo-rewrite.git"
if [ -d "$MIRROR_DIR" ]; then
  echo "Mirror directory $MIRROR_DIR already exists. Please remove or inspect it before continuing." >&2
  exit 2
fi

echo "Cloning mirror from origin ($ORIG_URL) into $MIRROR_DIR"
git clone --mirror "$ORIG_URL" "$MIRROR_DIR"
cd "$MIRROR_DIR"

echo "Preparing to run git-filter-repo in mode: $MODE"
if [ "$MODE" = "size" ]; then
  echo "Will strip blobs bigger than ${SIZE_MB}M"
  echo "DRY RUN: printing command to run (not executed):"
  echo
  echo "git filter-repo --strip-blobs-bigger-than ${SIZE_MB}M"
  echo
  echo "To execute, remove the echo and run the command above in $MIRROR_DIR"
elif [ "$MODE" = "paths" ]; then
  if [ ! -f "$WORKDIR/$PATHS_FILE" ]; then
    echo "Paths file not found: $WORKDIR/$PATHS_FILE" >&2
    exit 2
  fi
  echo "Will remove paths listed in: $WORKDIR/$PATHS_FILE"
  echo "DRY RUN: printing command to run (not executed):"
  echo
  while read -r p; do
    [ -z "$p" ] && continue
    echo "git filter-repo --path '$p' --invert-paths"
  done < "$WORKDIR/$PATHS_FILE"
  echo
  echo "To execute, remove the echo and run the printed command(s) in $MIRROR_DIR"
else
  echo "Unknown mode: $MODE" >&2
  exit 2
fi

echo
echo "After running git-filter-repo, inspect the rewritten mirror at: $MIRROR_DIR"
echo "You can clone from the mirror to verify tests:"
echo "  git clone file://$PWD/../$MIRROR_DIR ../verify-rewrite"
echo "  cd ../verify-rewrite && pytest -q"

echo
echo "If the rewritten history looks good and maintainers approve, you can push with:" 
echo "  cd $MIRROR_DIR" 
echo "  git push --force --all origin" 
echo "  git push --force --tags origin" 

echo
echo "Script complete. No destructive actions were performed. Review the suggested commands above." 

exit 0

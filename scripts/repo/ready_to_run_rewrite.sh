#!/usr/bin/env bash
set -euo pipefail
# ready_to_run_rewrite.sh
# Safe, maintainer-run helper to perform a history rewrite using git-filter-repo.
# This script is intended to be run locally on a maintainer machine against a
# freshly-created mirror clone (see instructions below). It will NOT push to
# origin automatically. It performs a dry-run option, and optionally writes a
# backup mirror tarball.

usage() {
  cat <<USAGE
Usage: $0 [--mirror-dir PATH] [--path-to-remove PATH] [--dry-run]

Examples:
  # 1) Mirror clone (on maintainer machine)
  git clone --mirror https://github.com/TaintedHorizon/Python_Testing_Vibe.git repo-mirror.git
  cd repo-mirror.git

  # 2) Dry-run rewrite locally
  ../scripts/repo/ready_to_run_rewrite.sh --mirror-dir . --path-to-remove 'Document_Scanner_Ollama_outdated/model_cache/craft_mlt_25k.pth' --dry-run

  # 3) If satisfied, run without --dry-run, then inspect and push to a preview remote
  ../scripts/repo/ready_to_run_rewrite.sh --mirror-dir . --path-to-remove 'Document_Scanner_Ollama_outdated/model_cache/craft_mlt_25k.pth'

Notes:
 - This script requires git-filter-repo to be installed and on PATH.
 - It will NOT perform any push; pushing must be done manually after review.
 - The script creates a timestamped backup tarball of the mirror before modifying it.
USAGE
}

MIRROR_DIR="."
PATH_TO_REMOVE=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mirror-dir) MIRROR_DIR="$2"; shift 2;;
    --path-to-remove) PATH_TO_REMOVE="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift 1;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if [[ -z "$PATH_TO_REMOVE" ]]; then
  echo "error: --path-to-remove is required" >&2
  usage
  exit 2
fi

if ! command -v git-filter-repo >/dev/null 2>&1; then
  echo "git-filter-repo not found on PATH. Install it first: https://github.com/newren/git-filter-repo" >&2
  exit 3
fi

pushd "$MIRROR_DIR" >/dev/null

# Make a timestamped backup tarball of the mirror (local, offline backup)
TS=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_TAR="../repo-mirror-backup-${TS}.tar.gz"
echo "Creating backup tarball: $BACKUP_TAR"
tar -czf "$BACKUP_TAR" . || true

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "DRY-RUN: simulating git-filter-repo on path: $PATH_TO_REMOVE"
  echo "git filter-repo --path '$PATH_TO_REMOVE' --invert-paths --dry-run"
  # Note: git-filter-repo has no builtin --dry-run; we simulate by showing planned command
  echo "(Dry-run complete) Review the backup at: $BACKUP_TAR"
  popd >/dev/null
  exit 0
fi

echo "Running git-filter-repo to remove path: $PATH_TO_REMOVE"
# Run the targeted removal
git filter-repo --path "$PATH_TO_REMOVE" --invert-paths

echo "Repacking and cleaning repository" 
git reflog expire --expire=now --all || true
git gc --prune=now --aggressive || true

echo "Sanity checks: verify blob and path no longer present"
echo "Checking blob presence (no output means not found):"
git rev-list --objects --all | grep -F "$(basename "$PATH_TO_REMOVE")" || true
echo "Listing recent refs and counts:"
git for-each-ref --format='%(refname) %(objectname)' | sed -n '1,120p' || true

echo "Rewrite complete locally. Please inspect the repository before pushing."
echo "Recommended next steps:" 
echo "  1) Clone the rewritten mirror into a test checkout and run test matrix."
echo "  2) If satisfied, push carefully to a preview remote and coordinate force-push to origin with maintainers."

popd >/dev/null
exit 0
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

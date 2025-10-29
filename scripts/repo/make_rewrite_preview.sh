#!/usr/bin/env bash
set -euo pipefail
# make_rewrite_preview.sh
# Create a mirror clone, run the rewrite helper to remove specified paths,
# produce a tarball of the rewritten mirror, and print SHA256 for provenance.

usage() {
  cat <<USG
Usage: $0 --paths "path1 path2" [--output DIR] [--repo-url URL]

Examples:
  # Create a preview tarball removing one path
  ./scripts/repo/make_rewrite_preview.sh --paths 'Document_Scanner_Ollama_outdated/model_cache/craft_mlt_25k.pth' --output ci_artifacts

Notes:
 - Requires `git` and `git-filter-repo` installed locally.
 - This script will NOT push anything. It creates a mirror clone and rewrites it locally.
 - The existing helper `scripts/repo/ready_to_run_rewrite.sh` is used to perform the rewrite.
USG
}

PATHS=""
OUTDIR="ci_artifacts"
REPO_URL="https://github.com/TaintedHorizon/Python_Testing_Vibe.git"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --paths) PATHS="$2"; shift 2;;
    --output) OUTDIR="$2"; shift 2;;
    --repo-url) REPO_URL="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if [[ -z "$PATHS" ]]; then
  echo "error: --paths is required" >&2
  usage
  exit 2
fi

mkdir -p "$OUTDIR"
TMP=$(mktemp -d)
mirror_dir="$TMP/repo-mirror.git"
echo "Cloning mirror into $mirror_dir"
git clone --mirror "$REPO_URL" "$mirror_dir"

echo "Creating timestamped backup tarball of original mirror"
TS=$(date -u +%Y%m%dT%H%M%SZ)
orig_tar="$OUTDIR/repo-mirror-orig-${TS}.tar.gz"
tar -C "$TMP" -czf "$orig_tar" "repo-mirror.git"
echo "Original mirror tarball: $orig_tar"

for p in $PATHS; do
  echo "Rewriting to remove path: $p"
  # Use the helper script to perform the rewrite in-place on the mirror
  bash ./scripts/repo/ready_to_run_rewrite.sh --mirror-dir "$mirror_dir" --path-to-remove "$p"
done

preview_tar="$OUTDIR/repo-rewrite-preview-${TS}.tar.gz"
echo "Creating preview tarball: $preview_tar"
tar -C "$TMP" -czf "$preview_tar" "repo-mirror.git"

sha=$(sha256sum "$preview_tar" | awk '{print $1}') || true
size=$(stat -c%s "$preview_tar" || true)

echo "Preview tarball: $preview_tar"
echo "SHA256: $sha"
echo "Size: $size bytes"

echo "Done. Inspect the tarball and the original backup before pushing any changes." 

exit 0

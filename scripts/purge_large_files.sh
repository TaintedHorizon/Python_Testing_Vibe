#!/usr/bin/env bash
set -euo pipefail

# purge_large_files.sh
# Helper to remove specific files from the repository history using a mirror clone
# and git-filter-repo. This script does not operate on your working repo; it
# creates a mirror, rewrites history there, and force-pushes the rewritten
# refs back to the origin remote. Use with caution and coordinate with
# collaborators.

REPO_URL="$(git config --get remote.origin.url || echo 'git@github.com:TaintedHorizon/Python_Testing_Vibe.git')"
MIRROR_DIR="repo-mirror.git"

if ! command -v git-filter-repo >/dev/null 2>&1; then
  echo "git-filter-repo not found. Install it with: pip install git-filter-repo" >&2
  exit 1
fi

echo "This will rewrite history in a mirror clone and force-push the rewritten refs to origin." 
read -p "Type YES to continue: " confirm
if [ "$confirm" != "YES" ]; then
  echo "Aborting." && exit 0
fi

echo "Cloning mirror..."
git clone --mirror "$REPO_URL" "$MIRROR_DIR"
cd "$MIRROR_DIR"

echo "Creating backup tag refs/original before rewrite..."
git for-each-ref --format='refs/original/%(refname:short)' refs/heads/ | xargs -r -n1 -I{} git update-ref {} refs/heads/{}

echo "Rewriting history: removing model files..."
git filter-repo --invert-paths \
  --paths Document_Scanner_Ollama_outdated/model_cache/craft_mlt_25k.pth \
  --paths Document_Scanner_Ollama_outdated/model_cache/english_g2.pth

echo "Verify refs and sizes (top objects)"
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | sed -n 's/^blob //p' | sort -k2nr | head -n 20

echo "Force-pushing rewritten refs to origin (all branches + tags)..."
git push --force origin --all
git push --force origin --tags

echo "Cleanup mirror..."
cd ..
rm -rf "$MIRROR_DIR"

echo "Done. The remote repository history has been rewritten and force-pushed."
echo "Notify collaborators: they must re-clone or run the re-sync steps in docs/REWRITE_HISTORY.md"

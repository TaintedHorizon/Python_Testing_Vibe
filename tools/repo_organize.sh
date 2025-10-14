#!/usr/bin/env bash
# tools/repo_organize.sh
# Safe repo organization script for Python_Testing_Vibe
# Usage:
#   ./tools/repo_organize.sh        # show dry-run preview
#   ./tools/repo_organize.sh --apply  # perform git mv operations

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APPLY=false
MOVE_TOOLS=false
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=true
fi
if [[ "${1:-}" == "--move-tools" ]] || [[ "${2:-}" == "--move-tools" ]]; then
  MOVE_TOOLS=true
fi

# Items considered allowed at repository root (top-level only)
KEEP=(
  ".git" ".github" ".gitignore" "README.md" "pytest.ini" "pyrightconfig.json" "start_app.sh" "validate_environment.py" "Python_Testing_Vibe.code-workspace"
)

# Items that belong under doc_processor/ (move candidates)
# We will only move directories that are not listed in KEEP and are not doc_processor itself.
MOVE_CANDIDATES=(
  "Document_Scanner_Gemini_outdated"
  "Document_Scanner_Ollama_outdated"
  "archive"
  "scripts"
  "docs/examples"
  "tools/download_manager" # leave tools/ but optionally move subfolders
  "tools/file_utils"
  "tools/gamelist_editor"
  "tools/sdcard_imager"
)

# Normalize candidates: only if they exist at root
declare -a TO_MOVE=()
for item in "${MOVE_CANDIDATES[@]}"; do
  if [[ -e "$ROOT_DIR/$item" ]]; then
    TO_MOVE+=("$item")
  fi
done

if [[ ${#TO_MOVE[@]} -eq 0 ]]; then
  echo "No candidate items found to move. Nothing to do."
  exit 0
fi

echo "Repository root: $ROOT_DIR"

echo "The following items are proposed to be moved into doc_processor/:"
for i in "${TO_MOVE[@]}"; do
  echo "  - $i -> doc_processor/$(basename "$i")"
done

echo
if ! $APPLY; then
  echo "DRY RUN (no changes made). Run with --apply to execute the moves."
  echo
  echo "Suggested git mv commands (preview):"
  for i in "${TO_MOVE[@]}"; do
    echo "git mv \"$i\" \"doc_processor/$(basename "$i")\""
  done
  exit 0
fi

# APPLY mode: perform git mv for each
for i in "${TO_MOVE[@]}"; do
  dest="doc_processor/$(basename "$i")"
  echo "Moving $i -> $dest"
  # create destination parent if not exists
  mkdir -p "$(dirname "$dest")"
  if [[ "$i" == tools/* && "$MOVE_TOOLS" != true ]]; then
    echo "Skipping move of $i because --move-tools was not provided"
    continue
  fi
  git mv "$i" "$dest"
done

echo "Move completed. Please review changes, run tests, and commit." 
exit 0

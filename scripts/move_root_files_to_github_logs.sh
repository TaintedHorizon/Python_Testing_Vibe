#!/usr/bin/env bash
set -euo pipefail

# Move accidental loose root files into .github/logs/ with a timestamped suffix.
# Safe and non-destructive: directories and allowed root files are skipped.

LOGDIR=.github/logs
mkdir -p "$LOGDIR"
timestamp=$(date -u +"%Y%m%dT%H%M%SZ")

# Permitted root-level filenames or directories (do not move these)
read -r -a allowed <<< ".git .github .gitignore README.md Makefile Python_Testing_Vibe.code-workspace\
pyrightconfig.json pytest.ini start_app.sh scripts dev_tools docs archive tools ui_tests .venv-ci .ruff_cache .pytest_cache .vscode LICENSE"

is_allowed() {
  local name="$1"
  for a in "${allowed[@]}"; do
    if [[ "$name" == "$a" ]]; then
      return 0
    fi
  done
  return 1
}

echo "Scanning repo root for loose files to move into $LOGDIR"

shopt -s nullglob
for f in *; do
  # skip if it's one of the allowed names
  if is_allowed "$f"; then
    #echo "Allowed: $f"
    continue
  fi

  # skip directories
  if [[ -d "$f" ]]; then
    continue
  fi

  # skip dotfiles (except .gitignore which is allowed above)
  if [[ "$f" == .* ]]; then
    continue
  fi

  dest="$LOGDIR/${f}.${timestamp}"
  echo "Moving $f -> $dest"
  mv -- "$f" "$dest"
done

echo "Done. Please inspect $LOGDIR for moved files."

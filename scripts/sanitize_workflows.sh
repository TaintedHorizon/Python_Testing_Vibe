#!/usr/bin/env bash
set -eu
printf "Sanitizing .github/workflows files...\n"
for f in .github/workflows/*.yml; do
  printf " - %s\n" "$f"
  # Backup then remove problematic lines: triple backticks, Begin/End Patch, github-actions-workflow
  sed -E -e '/^[[:space:]]*```/d' \
         -e '/^[[:space:]]*\*\*\* Begin Patch/d' \
         -e '/^[[:space:]]*\*\*\* End Patch/d' \
         -e '/github-actions-workflow/d' \
         "$f" > "$f".sanitized || true
  mv "$f".sanitized "$f"
done
printf "Sanitization complete.\n"

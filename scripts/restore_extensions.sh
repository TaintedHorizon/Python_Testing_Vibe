#!/usr/bin/env bash
set -euo pipefail

# Restore extensions from a backup file created by `code --list-extensions --show-versions`
# Usage:
#   ./scripts/restore_extensions.sh path/to/backup-file.txt

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 backup-file.txt" >&2
  exit 2
fi

BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 3
fi

echo "Restoring extensions from $BACKUP_FILE"

# The backup file contains entries like: publisher.extension@version
# We extract the extension id (before @) and install each one.
cut -d'@' -f1 "$BACKUP_FILE" | while read -r ext; do
  if [ -n "$ext" ]; then
    echo "Installing $ext..."
    code --install-extension "$ext" || echo "Failed to install $ext"
  fi
done

echo "Restore complete. Current installed extensions:"
code --list-extensions --show-versions

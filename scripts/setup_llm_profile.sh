#!/usr/bin/env bash
set -euo pipefail

# Setup a minimal LLM-focused extension set on the current machine (local or remote)
# Usage:
#   ./scripts/setup_llm_profile.sh [--remove-heavy]
# If --remove-heavy is provided, the script will uninstall a set of heavy devops/extensions
# that commonly cause background work (AWS Toolkit, Docker, Makefile tools). By default
# the script only installs the minimal LLM+Python set and creates a backup of current extensions.

BACKUP_FILE="vscode-extensions-backup-$(date +%Y%m%d-%H%M%S).txt"

echo "Exporting current extensions to $BACKUP_FILE"
code --list-extensions --show-versions > "$BACKUP_FILE"
echo "Backup complete."

echo "Installing recommended LLM + Python extensions..."
EXTS=(
  github.copilot
  github.copilot-chat
  google.geminicodeassist
  ms-python.python
  ms-python.vscode-pylance
  ms-python.debugpy
  ms-python.vscode-python-envs
)

for e in "${EXTS[@]}"; do
  echo "Installing $e..."
  code --install-extension "$e" || echo "Failed to install $e (continuing)"
done

if [ "${1:-}" = "--remove-heavy" ]; then
  echo "Removing heavy / background extensions (AWS, Docker, Makefile tools, GitHub Actions optional)..."
  HEAVY=(
    amazonwebservices.aws-toolkit-vscode
    ms-azuretools.vscode-docker
    ms-azuretools.vscode-containers
    ms-vscode.makefile-tools
  )
  for h in "${HEAVY[@]}"; do
    echo "Attempting to uninstall $h..."
    code --uninstall-extension "$h" || echo "Could not uninstall $h (maybe not installed or dependency)"
  done
fi

echo "Done. Current extensions:"
code --list-extensions --show-versions

echo
echo "Notes:
- This script modifies the environment where it is run. To act on your local desktop, run it on your desktop machine.
- Creating a VS Code Profile (recommended): open VS Code -> Command Palette -> Profiles: Create Profile... -> name it 'LLM'.
  Then use the Extensions view and pick 'Install in Profile' for the extensions you want in the LLM profile.
- The backup file contains the pre-change extension list; keep it safe to restore later."

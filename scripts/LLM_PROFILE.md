LLM Profile setup and restore
================================

This folder contains helper scripts to create a minimal LLM-focused extension setup and to restore extensions from a backup.

Files
- `setup_llm_profile.sh` - creates a backup of current extensions, installs recommended LLM + Python extensions and (optionally) removes heavy extensions with `--remove-heavy`.
- `restore_extensions.sh` - reinstalls extensions from a backup file produced by `code --list-extensions --show-versions`.

Usage
-----

1. Run the setup script on the machine you want to modify (local or remote):

```bash
./scripts/setup_llm_profile.sh
# or to also remove heavy background extensions:
./scripts/setup_llm_profile.sh --remove-heavy
```

2. Create a VS Code Profile (recommended):
   - In VS Code: Command Palette -> Profiles: Create Profile... -> name it `LLM`.
   - Use Extensions view to "Install in Profile" for the LLM extensions.

3. If you need to restore previous extensions:

```bash
./scripts/restore_extensions.sh vscode-extensions-backup-YYYYMMDD-HHMMSS.txt
```

Notes
-----
- These scripts use the `code` CLI; run them where `code` is available and points to the desired VS Code install (local or remote).
- The restore script extracts extension IDs from the backup (it ignores pinned versions) and attempts to reinstall them.
- Creating profiles via the UI is recommended because the CLI does not universally support profile-level installs across all VS Code versions.

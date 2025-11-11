CONTRIBUTING: Archives & Local Backups
====================================

Purpose
-------
This short note explains how to keep large backups and local archive files out of the main repository so CI and linters are not impacted.

Guidelines
----------
- Do NOT commit generated or archival files (database snapshots, exported PDFs, large image archives) into the repo.
- Use the app-configurable backup directory for DB/backups: set `DB_BACKUP_DIR` to an absolute path outside the repository (for example `/var/lib/doc_processor/db_backups` or `~/.local/share/doc_processor/db_backups`).
- For temporary developer backups avoid committing files named `*_backup.py` — prefer storing these in an external folder or backing them up to an artifact store.
- Add any long-lived archives to a personal storage location (S3, GCS, NFS) and reference them in docs instead of keeping them in `archive/`.

Why
---
Keeping archives and backups out of the repository prevents:

- CI failures from linters scanning historical/archival code (example: `flake8` F824 errors from large backup files).
- Accidental commits of large binary artifacts that bloat the repo.

What this repo enforces
-----------------------
This repository includes a minimal `.gitignore` entry that excludes common backup/archive patterns (for example `*_backup.py` and `doc_processor/archive/`). If you need to keep a local copy for debugging, keep it outside the repo or in a named branch that you and the team agree to keep private.

If you have a legitimate reason to add a file under `archive/` that should be tracked, open an issue and explain the retention needs. We'll review on a case-by-case basis.

Minimal workflow for developers
-------------------------------
1. Create backups outside the repo:

```bash
mkdir -p ~/doc_processor_backups
cp doc_processor/dev_tools/some_script.py ~/doc_processor_backups/some_script.py.bak
```

2. If you accidentally committed a backup, remove it and push a corrective commit, then call out the accidental commit in PR description so we can avoid reintroducing the file.

Contact
-------
If you're unsure where to keep a file, open an issue or ping the maintainers (`@TaintedHorizon`).

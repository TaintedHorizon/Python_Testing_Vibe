Archive policy and housekeeping guidance
=====================================

Purpose
-------
This document describes the repository's policy for handling transient or "loose" files that should not live at the repository root.

Policy (short)
--------------
- Do not add transient files directly at the repository root in a Pull Request.
- Place archival/logs files under `.github/logs/` or another curated folder that is specifically intended for archival artifacts.
- Source and support files required for the application or CI must remain in their appropriate tracked locations (not archived).

Recommended workflow for cleanup
--------------------------------
1. Identify which files are truly transient (logs, local exports, editor workspace files). Those belong in `.github/logs/`.
2. If you need to archive several files, create a branch and a PR that only modifies files under `.github/` (for example, add an entry to `.github/logs/` or add a note in `.github/ARCHIVE_LOGS.md`).
3. Do not delete tracked source files in the same PR that archives logs; keep source-restores and refactors in separate PRs.

If the files are application source or CI scripts, they must remain tracked at their appropriate location. If you are not sure, open an issue or tag the repository maintainers.

Example: quick safe archive (local, non-destructive)
--------------------------------------------------
Run the provided script from the repo root to move loose root files into `.github/logs/` with timestamped suffixes. This script is non-destructive aside from moving files, and produces a clear audit trail:

```bash
# from repo root
bash ./scripts/move_root_files_to_github_logs.sh
```

After the move, open a PR that only contains the changes you intend to keep tracked (preferably a PR that documents the cleanup under `.github`). Avoid making large refactors and archival moves in a single PR that also changes source files.

Questions or exceptions
----------------------
If you believe a file should remain at repo root (for example, it's a required source file), open an issue or tag the maintainers and we will handle it explicitly rather than silently archiving.

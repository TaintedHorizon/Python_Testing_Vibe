# Contributing — quick guide

This short guide points contributors to the canonical places to find contribution rules for the repository and the `doc_processor` app.

1. Project-level contribution guidance

- The project maintains a short, specific note about archival/backups in `.github/CONTRIBUTING-ARCHIVES.md`. This covers where to keep heavy backup files so CI and linters are not impacted. Please read it before adding any large files or backup scripts to the repository.

2. Repo-level guidelines

- For repository-wide contribution policies (pull-request workflow, branch naming, CI expectations), consult the top-level `CONTRIBUTING.md` and the GitHub workflows docs in `.github/workflows/README.md`.

3. App-specific contributing

- The `doc_processor/` package includes its own `CONTRIBUTING.md` that covers testing, environment setup, and code style for runtime changes. If you are changing any runtime behavior (routes, processing, DB schema), follow `doc_processor/CONTRIBUTING.md` and add tests where practical.

4. How to open a small documentation PR

- Create a short branch named `chore/docs-*` (for non-functional doc edits).
- Make small focused changes; prefer multiple small PRs over a single large doc-sweep.
- Add a short PR description listing files changed and motivation.

5. Where to put backups and heavy artifacts

- Use an external storage location (S3, GCS, NFS) or a local folder outside the git repository (for example `~/doc_processor_backups` or `/var/lib/doc_processor/db_backups`).
- Do not commit database files, model weights, or large image archives directly to the repo. If you must version large files, use Git LFS and get prior approval.

6. Links

- `.github/CONTRIBUTING-ARCHIVES.md` — repository archival backup guidance
- `doc_processor/CONTRIBUTING.md` — app-specific contribution & test guidelines
- `docs/USAGE.md` — usage documentation

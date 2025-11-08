# Archived workflows — README

This directory holds archived GitHub Actions workflow YAML files. Workflows are archived here when they are:

- Superseded by a newer workflow
- Rarely used (very infrequent runs)
- Duplicated or replaced by consolidated workflows

Why we keep an archive
----------------------
- Preserves history for quick rollback or inspection.
- Makes it easy to restore a workflow if a dependent process reappears.

How to use
----------
1. Before archiving, open a small docs-first PR that includes:
   - `.github/OWNERS.md` (if the owners list needs updates) and/or
   - `docs/ARCHIVE_PROPOSAL.md` describing the rationale.
2. After the docs PR is reviewed and approved by an owner, open the archival PR that moves workflow file(s) into this directory.
3. Keep archival PRs small (1–5 files); validate with `validate-workflows` and address any issues before merging.

Restore process
---------------
To restore an archived workflow, move the file back to `.github/workflows/` in a new PR and request owner review.

Naming and metadata
-------------------
- When moving files here, add a short header comment in the YAML with the date and a one-line reason, e.g.:

  # Archived on 2025-11-06 — replaced by `ci-fast-path.yml` to reduce install time

Checklist for reviewers
-----------------------
- Is the rationale documented (link to issue or design notes)?
- Has the owning team been requested for review? (see `.github/OWNERS.md`)
- Is there a rollback plan included in the PR description?

Contact
-------
<!-- PR metadata: branch=chore/docs-archive-owners, created-for-pr -->
 If you're unsure whether to archive a workflow, ping the repo owner listed in `.github/OWNERS.md`.

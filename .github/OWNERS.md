# Repository owners and workflow archive policy

This file documents the owners and the process we follow when archiving GitHub Actions workflows.

Owners
------
- Repository owner: @repo-owner (assign PRs to this user for approval; replace with the real username)
- CI/Infra: @ci-owner (responsible for CI workflow changes and branch-protection settings)

If you are not an owner and need to request an archive/move/restore, open a small _docs-first_ PR that:

1. Adds or updates `.github/OWNERS.md` if ownership needs changing.
2. Adds `docs/ARCHIVE_PROPOSAL.md` or updates an existing proposal with the rationale.
3. Mentions the owner(s) in the PR description and requests review.

Archive policy (summary)
------------------------
- Always prefer a docs-first PR that explains why the workflow should be archived.
- Keep archival PRs small (1–5 files) so the validator can quickly run and triage issues.
- Each archival PR must include:
  - A short rationale and a link to the owning team discussion (if any).
  - A simple rollback plan (how to restore files from the PR branch or main history).
  - A note specifying whether the workflow is being archived because it's stale, duplicated, or replaced.

Process for archival
--------------------
1. Create a branch named `chore/archive-<short-topic>`.
2. Add the docs-first changes (OWNERS/ARCHIVE_PROPOSAL or update existing docs).
3. Open a PR and request review from an owner.
4. After approval, create small archival PR(s) that move workflows from `.github/workflows/` to `.github/workflows/archive/`.
5. Run the `validate-workflows` workflow (it is required on `main`) and address any validator errors.
6. Merge when CI is green. If a post-merge problem appears, revert the merge and follow the rollback plan.

Restoration
-----------
To restore an archived workflow:

1. Create a branch `chore/restore-<workflow-name>`.
2. Move the workflow file back into `.github/workflows/` and add a brief justification.
3. Open a PR and request review from the original owner.

Notes
-----
- Do not delete archived workflows immediately; keep them in `.github/workflows/archive/` for at least one release cycle so we can confirm nothing depends on them.
- For any questions, @repo-owner is the contact point.

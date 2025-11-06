# Archive / Workflow Cleanup Proposal

This PR proposes a low-risk, documented cleanup of stale or duplicate GitHub Actions workflows.

Summary of findings (from repo):

Top-level workflows:
- ci-fast-path.yml
- ci-rewrite.yml
- ci-smoke.yml
- ci.yml
- collect-action-logs.yml
- diagnose-smoke-and-upload.yml
- e2e.yml
- heavy-deps.yml
- manual-e2e.yml
- manual-smoke.yml
- manylinux-build.yml
- merge-prs.yml
- playwright-e2e.yml
- push-smoke.yml
- smoke.yml
- validate-workflows.yml

Archived workflows (.github/workflows/archive):
- ci-bisect-1.yml
- ci-bisect-2.yml
- ci-bisect-3.yml
- ci-bisect-4.yml
- ci-bisect-5.yml
- ci-bisect-5-fixed.yml
- ci-clean.yml
- ci-debug.yml
- ci-smoke-temp.yml
- validate-smoke-dispatch.yml
- validate-smoke-manual-v2.yml
- validate-smoke-manual.yml
- validate-smoke.yml

Proposed actions (low-risk):

1. Confirm owners for the following workflow groups and add an `OWNERS.md` entry in `.github/`:
   - CI workflows (ci.yml, ci-rewrite.yml, ci-fast-path.yml, heavy-deps.yml)
   - E2E/workflow tests (e2e.yml, playwright-e2e.yml, manual-e2e.yml)
   - Smoke and diagnostic workflows (smoke.yml, ci-smoke.yml, diagnose-smoke-and-upload.yml)
   - Cleanup/experimental (anything in `archive/`)

2. Move unused or experimental files to `.github/workflows/archive/` with a one-line reason and the original author.
   - Candidate moves already in `archive/` appear to be historical bisection/diagnostic workflows.

3. Add a short `archive/README.md` describing why items are archived and the rollback plan.

4. Run `validate-workflows` after each cleanup PR to ensure no syntax regressions.

Acceptance criteria for the cleanup PR(s):
- No production workflows are deleted without an owner sign-off.
- Each moved file has a one-line rationale in the commit/PR.
- `validate-workflows` passes on the cleanup branch.

Next steps suggested:
- Maintainer review of this proposal.
- If accepted, open small PRs that only move files (one directory or file group per PR) so `validate-workflows` and CI are easy to triage.


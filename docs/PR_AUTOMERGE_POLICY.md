PR Automerge Policy — Assistant Responsibilities
===============================================

Goal: When the assistant asks to open a PR and you approve, the PR must be opened in a state that will
actually automerge (no manual "why isn't this automerging" follow-ups).

Required pre-PR checks (assistant MUST perform before creating a PR requesting automerge):

1. Run local preflight script

   ```bash
   ./scripts/preflight_local.sh
   ```

   - This runs syntax checks, critical flake8 rules for `doc_processor`, a root-file policy check
     (compares to `origin/main`), and `tools/pr_preflight_validate.py` if present. The script exits
     non-zero on required failures; assistant must fix failures or not open an automerge PR.

2. Run unit tests (or confirm they run in CI with FAST_TEST_MODE when relevant)

   ```bash
   cd doc_processor
   pytest -q --ignore=tests/e2e -m "not e2e"
   ```

   - If tests fail, assistant must fix commits in the branch before requesting automerge.

3. Ensure branch is up to date with `origin/main`

   ```bash
   git fetch origin
   git rebase origin/main
   ```

   - Resolve merge conflicts locally and re-run preflight and tests.

4. Add automerge trigger to PR title or body

   - Include `[automerge]` in the PR title or body (the repo's labeler action will add the `automerge` label),
     or ensure the PR author is in the allowlist (repo owner or `svc-scan`).

5. Do NOT modify workflow files if requesting fast-track

   - PRs that change `.github/workflows/` are skipped by the auto-merge flow for safety.

6. Create PR using the provided template

   - The repository includes a pull request template that lists the pre-PR checklist; assistant must use it
     and complete the checklist before opening a PR requesting automerge.

Assistant operational steps (what the assistant will do every time):

- Run `./scripts/preflight_local.sh` and fail fast if it reports errors.
- Run `pytest` in `doc_processor` unless the change is docs-only.
- Rebase branch onto `origin/main` if out of date; run preflight again.
- Create the PR using the `.github/PULL_REQUEST_TEMPLATE.md`; include `[automerge]` in the PR title
  if you requested automerge.
- Confirm the PR is labeled `automerge` (the existing `label-automerge.yml` job will add it when appropriate).
- Notify you with the PR URL and a short checklist confirming preflight and tests passed locally.

If any of these steps fail, the assistant will not open an automerge PR and will instead present the failure
output and a proposed fix for your approval.

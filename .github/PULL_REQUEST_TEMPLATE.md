<!--
PR template: follow the checklist below. If you request automerge, include [automerge]
in the PR title or body and ensure all preflight checks pass before opening the PR.
-->

# Summary

Describe the change in one sentence.

## Pre-PR checklist (required for any PR requesting automerge)

- [ ] I ran the local preflight checks: `./scripts/preflight_local.sh` and fixed any errors.
- [ ] I ran unit tests locally (or ensured CI will run them): `cd doc_processor && pytest -q --ignore=tests/e2e`
- [ ] The branch is rebased/merged with `origin/main` and there are no unexpected root-level files.
- [ ] If I requested automerge, the PR title or body contains `[automerge]`.
- [ ] This PR does not modify `.github/workflows/` (workflow changes are **not** fast-tracked).

If you want the PR to automerge, include `[automerge]` in the title or body and make sure the
preflight checks above pass before creating the PR. The repository's `auto-merge-on-smoke` workflow
will only attempt a merge after `CI Smoke` completes successfully and branch-protection checks allow it.

## What changed

Provide a brief description of the change and any notable details.

## Testing

Explain how this was tested locally.

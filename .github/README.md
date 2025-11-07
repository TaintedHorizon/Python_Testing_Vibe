## Repository workflow helpers and validator

This repository includes a lightweight workflow validator and helper scripts under `.github/scripts/` to make working with GitHub Actions safer and more reliable.

Key pieces
- `validate-workflows.yml` — a workflow that runs on pull requests, manual dispatch, and pushes to `main` (and `chore/cleanup-workflows`). It runs the local YAML validator to catch malformed or duplicate workflow files early.
- `.github/scripts/validate_workflow.py` — the validator invoked by the workflow (uses PyYAML).
- `.github/scripts/add_required_check.sh` — helper to add a required status-check context to branch protection. Supports `--dry-run`.
- `.github/scripts/poll_run.sh` — helper to poll workflow run status and fetch logs on failure.

Why this exists
- Prevents broken workflow YAML from being merged to `main`.
- Makes CI stable by allowing a fast-path (trimmed deps) and keeping heavy installs opt-in.
- Adds tooling to diagnose and recover failing runs.

How to run the validator locally

1. Install PyYAML in a virtualenv or system Python:

```bash
python -m venv .venv
source .venv/bin/activate
pip install PyYAML
```

2. Run the validator against the workflows directory:

```bash
python .github/scripts/validate_workflow.py .github/workflows/*.yml
```

Adding the validator as a required check (admin action)

The repository includes a helper to add the validator as a required status check on a branch. This requires `gh` CLI authenticated as a user with admin permissions and `jq` installed. The helper now supports `--dry-run` so you can preview the payload.

Example (dry-run):

```bash
bash .github/scripts/add_required_check.sh --repo TaintedHorizon/Python_Testing_Vibe --branch main --context validate-workflows --dry-run
```

Example (apply):

```bash
bash .github/scripts/add_required_check.sh --repo TaintedHorizon/Python_Testing_Vibe --branch main --context validate-workflows
```

Notes and safety
- The helper constructs a minimal, API-acceptable payload to avoid schema validation errors.
- When changing branch protection via script, always inspect the payload (use `--dry-run`) and save a copy of the original protection if you may need to restore it.

Monitoring runs

Use the GitHub CLI to list and inspect recent runs:

```bash
gh run list -R TaintedHorizon/Python_Testing_Vibe --limit 30
gh run list -R TaintedHorizon/Python_Testing_Vibe --workflow validate-workflows.yml --limit 20
gh run view <RUN_ID> -R TaintedHorizon/Python_Testing_Vibe --log
```

If you have questions or want me to revert a change, ask and I can prepare a safe dry-run payload before applying any modification.

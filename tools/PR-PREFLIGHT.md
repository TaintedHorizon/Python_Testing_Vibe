PR preflight validation
======================

This small helper verifies branch-protection required status contexts (on `main`) are present as job `name:` values in the repository workflows under `.github/workflows/`.

Why
---
GitHub branch-protection requires exact strings for required status checks. Workflow job `name:` values produce the check-run names that appear on PRs. Mismatches will prevent auto-merge.

Usage
-----
Run the script from the repository root:

```bash
tools/pr_preflight_validate.sh
```

If your environment can't detect the current repo, pass `--repo owner/repo`:

```bash
tools/pr_preflight_validate.sh --repo TaintedHorizon/Python_Testing_Vibe
```

Exit codes
----------
- 0: all required contexts are found as workflow job names
- 2: repository could not be detected or supplied
- 3: one or more required contexts are missing

Notes
-----
- The script uses the `gh` CLI to query branch-protection; ensure `gh` is authenticated.
- It uses a simple YAML scanning approach and may not parse complex workflow constructs. It's purposely lightweight to avoid adding dependencies.

Advanced usage
--------------
- There's a stricter Python validator available: `tools/pr_preflight_validate.py`. It uses PyYAML and will expand matrixed job names (for example, `Unit Tests (Python ${{ matrix.python-version }})` -> `Unit Tests (Python 3.11)`). Install PyYAML with:

```bash
pip install pyyaml
```

- To create PRs with automatic preflight and optional auto-merge, use `tools/create_pr_with_preflight.sh`.

Default behavior

- As requested, the agent now auto-opens PRs and enables auto-merge by default for PRs it creates. The script defaults to enabling auto-merge and non-interactive confirmation so the agent can create and merge PRs autonomously when required checks pass.

Example (explicit non-interactive auto-merge):

```bash
tools/create_pr_with_preflight.sh --branch chore/my-fix --title "chore: my fix" --body-file pr_body.md --commit-msg "WIP" --enable-auto-merge --yes
```

If you want to opt out of non-interactive auto-merge for a particular run, set the environment variable `AUTO_YES=0` or pass `--no-auto` when invoking the script (the script treats explicit flags and env vars as overrides).

Git alias suggestion
--------------------
You can add a git alias to quickly run the preflight and create a PR from the current branch. Add to your `~/.gitconfig`:

```ini
[alias]
	pr-create = !tools/create_pr_with_preflight.sh --branch $(git rev-parse --abbrev-ref HEAD) --title "$(git log -1 --pretty=%B)"
```

This alias is a convenience only; the script will still validate required checks before creating the PR.

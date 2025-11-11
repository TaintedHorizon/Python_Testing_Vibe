PR Merge Helper (tools/pr-merge-helper.sh)
=========================================

Purpose
-------
This script automates maintainer workflows for rebasing and merging open pull requests using the `gh` CLI and local `git`.

Key features
------------
- Lists open PRs and orders them by mergeability.
- Attempts GitHub's `update-branch` API when helpful.
- Falls back to a local rebase flow: fetches PR branch, rebases onto `origin/main`, runs quick checks, and force-pushes the rebased branch (with confirmation).
- Posts comments to PRs to notify authors about actions taken.

Safety and usage
----------------
- Intended for maintainers only. It can perform destructive operations (force-push).
- The script supports a dry-run mode: `./pr-merge-helper.sh --dry-run` which will simulate remote-changing operations and post informative comments instead of pushing.
- Configure repository and branch via environment variables if needed:
  - `OWNER` (default: `TaintedHorizon`)
  - `REPO` (default: `Python_Testing_Vibe`)
  - `MAIN` (default: `main`)

Requirements
------------
- `gh` (GitHub CLI) authenticated and available in PATH
- `jq` for JSON processing
- `git` available and executed from the repository root

Recommended workflow
--------------------
1. Review the PR list produced by the script.
2. Use `--dry-run` initially to verify planned actions.
3. Run without `--dry-run` when you are ready; the script will prompt before any force-push.

Notes
-----
- The script creates local branches named `<pr-branch>-local` during rebase operations and a `backup/<pr-branch>` ref when available.
- Keep this script in `tools/` and limit execution to trusted maintainers.
- Consider integrating parts of the safe, non-destructive functionality into a GitHub Action if desired.

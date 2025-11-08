# Helper scripts for CI monitoring and automation

This directory contains small helper scripts used during CI triage and repository automation. These are operational, low-risk utilities intended to be run by repository maintainers when investigating CI flakes or exercising the docs-fast-path automation.

Files (common):

- `watch_prs.sh` - background watcher that polls a short list of PRs and logs state transitions to `.github/logs/pr_watch.log`. Saves its PID to `.github/scripts/watch_prs.pid` and stdout to `.github/logs/pr_watch_stdout.log`.
- `monitor_validate_runs.sh` / `monitor_validate_runs.py` - a periodic monitor that lists `validate-workflows` runs and saves failing-run logs to `.github/logs/` for later triage. Stdout lives in `.github/logs/monitor_stdout.log`.
- `auto_merge_poll_52.sh` - an older poller used to attempt merging PR #52. It should be stopped and removed if repo-level Auto-Merge is enabled.

Where logs and PID files live:

- `.github/logs/` – aggregated logs created by the helper scripts (watcher stdout, monitor stdout, captured failing-run logs, auto-merge logs).
- `.github/scripts/*.pid` – PID files for background processes started by maintainers. If a PID file exists, you can check and stop the process with `kill $PID`.

Quick operational notes

- To see the watcher's live output (if it was started with nohup):

  tail -n +1 -f .github/logs/pr_watch_stdout.log

- To stop the watcher safely (if a PID file exists):

  if [ -f .github/scripts/watch_prs.pid ]; then
    pid=$(cat .github/scripts/watch_prs.pid)
    kill "$pid" && rm -f .github/scripts/watch_prs.pid
  else
    echo "No watcher PID file found.";
  fi

- To collect validator failure logs (if any):

  ls -la .github/logs | sed -n '1,200p'
  # Look for files named like: validate-fail-<run-id>.log

Security & safety

These scripts use the GitHub CLI (`gh`) and repository tokens; they are intended for maintainers only. They do not modify repository content by default (except the optional merge poller which should be retired once repo Auto-Merge is enabled).

If you plan to run or modify any of them, do so from a local shell with appropriate credentials and consider running in `--dry-run` mode where available.

If you want, I can open a tiny docs-only PR for this file (safe to auto-merge via docs-fast-path). Want me to do that now?
poll_run.sh - polling helper for GitHub Actions runs

Usage
-----
Requires:
- gh CLI (https://cli.github.com/) authenticated (gh auth login)
- jq installed

Basic usage:

```bash
.github/scripts/poll_run.sh <run-id> --repo TaintedHorizon/Python_Testing_Vibe
```

Options:
- --repo owner/repo    (defaults to TaintedHorizon/Python_Testing_Vibe)
- --interval N         (seconds between polls, default 10)
- --retries N          (max attempts before timeout, default 60)

Behavior:
- Polls the run status until it becomes `completed`.
- If the run conclusion is `success` or `neutral`, exits 0.
- If the run conclusion is non-success, prints the run logs (via `gh run view --log`) and exits 1.
- If the run is not found or polling times out, exits 2.

Example:

```bash
# Poll run 19042679649 in this repo every 15s for up to 120 attempts
.github/scripts/poll_run.sh 19042679649 --interval 15 --retries 120
```

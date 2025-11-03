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

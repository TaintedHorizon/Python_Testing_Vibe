Agent Auto-Merge Policy

The project automation agent (GitHub Copilot automation scripts and the `tools/create_pr_with_preflight.sh` helper)
will automatically request "auto-merge" for any pull request it creates. This behavior is intended to reduce
operator friction for routine housekeeping PRs that the agent opens and will only request auto-merge — it does
NOT bypass branch protection rules or required human reviews.

How it works
- The `tools/create_pr_with_preflight.sh` script will run the preflight validator, create the PR, and request
  auto-merge automatically (non-interactive) when enabled.
- The script respects environment variables and branch-protection rules. If branch protection prevents auto-merge,
  the request will be queued but merge will not occur until required checks/reviews are satisfied.

If you would like the agent to stop requesting auto-merge, set the environment variable `ENABLE_AUTOMERGE_ENV=0`
when invoking the `tools/create_pr_with_preflight.sh` helper, or edit the script to change the default behavior.

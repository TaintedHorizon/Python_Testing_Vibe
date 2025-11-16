# Agent Auto-Merge Policy

This repository contains an automation agent (GitHub Copilot assistant) that opens pull requests
for routine changes (cleanup, small tooling updates, CI fixes). To reduce manual steps, the
agent will request *auto-merge* for any pull request it opens by default.

How this is implemented

- The helper script used to create PRs is `tools/create_pr_with_preflight.sh`.
- By default the script now requests auto-merge non-interactively and uses the `squash`
  merge method.
- Environment variables to override behavior:
  - `ENABLE_AUTOMERGE_ENV=0` — disable auto-merge requests for a run.
  - `MERGE_METHOD_ENV=<merge|squash|rebase>` — change merge method for auto-merge requests.
  - `AUTO_YES_ENV=0` — require interactive confirmation (not used by the agent by default).

Opting out or changing behavior

- To prevent the agent from requesting auto-merge for *all* PRs it creates, set
  `ENABLE_AUTOMERGE_ENV=0` in the environment where the agent's tooling runs.
- To change the default merge method, set `MERGE_METHOD_ENV` to `merge` or `rebase`.

Notes and caveats

- Requesting auto-merge does not guarantee an immediate merge. The repository's branch protection
  rules and required CI status checks still apply; auto-merge will only be completed when all
  required checks are green and branch protection allows merging.
- Auto-merge requests require the authenticated GitHub token used by the `gh` CLI to have
  permission to enable auto-merge. If you see "permission denied" or similar errors from the
  automation, update the token permissions.
- The agent will log PR creation events into `.github/logs/agent-pr-log.md` so there is an audit
  trail for PRs opened and the agent's actions.

If you want me to change the default behavior (for example, always use `merge` instead of
`squash`, or to disable auto-merge entirely), tell me and I'll update `tools/create_pr_with_preflight.sh` accordingly.

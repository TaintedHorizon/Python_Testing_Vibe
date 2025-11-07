Docs fast-path merge-bot
========================

This workflow watches for the `docs-fast-path` check run to complete with `success`. When that happens it:

- Finds the PR(s) associated with the commit the check was created for.
- Verifies `docs-fast-path` is successful for that PR head.
- If branch protection requires PR reviews, checks for at least one `APPROVED` review.
- Attempts a squash merge via the GitHub API and leaves a comment if merge fails.

Notes and safety
- The job runs with the default `GITHUB_TOKEN` and requires `pull-requests: write` permission. That token cannot bypass branch protection that enforces required reviews unless `enforce_admins` is false and token has admin rights — this workflow explicitly checks for approvals and will not merge without them.
- For stricter policies (e.g., required code owners), this workflow will not override those rules.

How to use
- Merge this PR to add the merge-bot. It will run for `docs-fast-path` check successes.
- Optionally tune the approval policy inside the workflow: e.g., require 2 approvals, check review authors, or restrict to certain teams.

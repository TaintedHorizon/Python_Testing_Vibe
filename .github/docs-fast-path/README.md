Docs fast-path
================

This repository includes a small, fast GitHub Actions workflow that detects "docs-only" pull requests and creates a lightweight check run named `docs-fast-path`.

What it does
- Runs on pull request open/synchronize/reopen.
- Computes the changed files relative to the PR base.
- If all changed files match docs or repository metadata patterns (for example: `docs/**`, `*.md`, `.github/**`), the workflow creates a check run `docs-fast-path` with conclusion `success`.
- Otherwise the workflow creates `docs-fast-path` with conclusion `neutral`.

How to use
- This workflow by itself does not change branch-protection rules. If you want docs-only PRs to merge automatically, you can either:
  - Enable repository Auto-Merge (already supported) and rely on a merge policy that accepts `docs-fast-path` when present; or
  - Add a separate merge-bot / action that merges PRs labeled `docs-only` after the `docs-fast-path` check passes and necessary approvals are present.

Security notes
- The workflow creates a check run using the default `GITHUB_TOKEN` which has the `checks: write` permission in this repository's actions context. That is required for the check run creation.
- Do not treat `docs-fast-path` as a substitute for human review on sensitive content. Consider pairing it with code-owner policies or review requirements for critical paths.

Next steps (recommended)
1. If you want docs PRs to merge automatically, enable repository Auto-Merge (done) and consider adding a small merge-bot that only merges PRs whose `docs-fast-path` check is `success` and which meet approval requirements.
2. Optionally tune the file globs the workflow treats as "docs/metadata" to match your repo layout.

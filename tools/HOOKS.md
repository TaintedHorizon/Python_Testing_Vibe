Local Git hooks

- `tools/install_pr_preflight_hook.sh` — Installs a local `.git/hooks/pre-push` hook
  that runs the repository's preflight validator (`tools/pr_preflight_validate.py`) before
  allowing a push. This is a convenience for developers to catch CI/workflow mismatches
  early on their machines.

Usage

1. Install the hook:

   ```bash
   ./tools/install_pr_preflight_hook.sh --repo owner/repo
   ```

2. To bypass the hook for a single push (e.g., CI-only changes), set an env var:

   ```bash
   SKIP_LOCAL_HOOK=1 git push
   ```

Notes

- The hook is intentionally local (written to `.git/hooks/pre-push`) and is not committed to
  the repository, so each developer opt-in is required.
- The script will exit non-zero and prevent the push if the preflight validator reports
  issues. This keeps your local pushes aligned with the same checks the PR helper runs.

# Developer Git Hooks

We provide a convenience script to install a local `pre-push` hook that runs the repository's
preflight validator before allowing a push. This helps catch CI/workflow mismatches early on
your workstation.

Install the hook locally with:

```bash
make install-preflight-hook
# or
./tools/install_pr_preflight_hook.sh --repo TaintedHorizon/Python_Testing_Vibe
```

To skip the hook for a single push (for example, when updating CI workflows), use:

```bash
SKIP_LOCAL_HOOK=1 git push
```

The hook is intentionally local-only (written to `.git/hooks/pre-push`) and is not committed,
so each developer must opt in.

Notes
- The installer will create `.git/hooks/pre-push` and make it executable.
- The hook runs `tools/pr_preflight_validate.py` and will abort the push if the validator exits non-zero.
- To bypass the hook permanently, set `SKIP_LOCAL_HOOK=1` in your environment or remove the hook file.

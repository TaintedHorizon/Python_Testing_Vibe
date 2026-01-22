Pre-PR Local Preflight Checks
=============================

Run the following before opening a PR to avoid common CI rejections:

From the repository root:

```bash
./scripts/preflight_local.sh
```

What the script does:

- Quick Python syntax check for all tracked `.py` files
- Runs critical `flake8` checks (E9,F63,F7,F82) for files under `doc_processor/` (if `flake8` is installed)
- Detects added root-level files compared to `origin/main` (requires `origin/main` fetched locally)
- Runs `tools/pr_preflight_validate.py` if present

If any check fails, fix the reported issues locally and re-run the script before opening a PR. This
reduces the number of failing GitHub Actions runs for checks such as `Block new root files`, `CI Basic Checks`,
and the `Preflight Validator`.

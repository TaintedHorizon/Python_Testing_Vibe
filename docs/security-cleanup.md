Security cleanup and artifact removal
=====================================

Goal
----
Remove committed CI/test artifacts that may contain secrets or tokens and provide safe steps to clean history and rotate secrets.

High level steps
----------------
1. Inspect the files you will remove.
2. Remove them from the repository and add appropriate `.gitignore` entries.
3. If any secret was committed, rotate it immediately (GitHub PATs, AWS keys, etc.).
4. If you need to remove secrets from git history, use `git filter-repo` or `bfg` with care.

Safe commands (run from repo root)
----------------------------------
# 1) Show candidate files (dry-run)
# This looks for common artifact dirs we added to .gitignore.
find doc_processor/ci_logs -type f || true
find doc_processor/tests/e2e/artifacts -type f || true

# 2) Remove files from git while keeping them locally (recommended first)
# This will stop tracking the files but not delete them from your disk.
# Review the listed files first before running.
# IMPORTANT: run these only if you are sure you don't need the files in the repo.

git rm --cached -r doc_processor/ci_logs || true
git rm --cached -r doc_processor/tests/e2e/artifacts || true

# 3) Commit the removals and updated .gitignore
git add .gitignore
git commit -m "chore: remove committed CI/test artifacts and ignore artifact dirs"

# 4) Push the commit
git push origin <branch>

If you must remove these files from repository history (e.g., they contained a real secret), use
`git filter-repo` (preferred) or BFG. Example with git filter-repo:

# Install git-filter-repo if needed
pip install git-filter-repo

# Backup current repo first (very important)
git clone --mirror . ../repo-backup.git

# Rewriting history to remove the paths
git filter-repo --path doc_processor/ci_logs --path doc_processor/tests/e2e/artifacts --invert-paths

# After this, force-push to origin (coordinate with your team and understand the impact)
# git push --force

Rotate any exposed secrets immediately:
- GitHub: delete the token or PAT, create a new one, update Actions or other consumers.
- AWS: rotate keys, update any deployed configurations.

Questions or help
-----------------
If you'd like, I can generate the exact `git rm` commands for the specific files found in this repo, or prepare a branch that removes them for you to review. Tell me which you prefer.

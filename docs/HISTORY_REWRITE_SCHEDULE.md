# Proposed History Rewrite Schedule & Checklist

This document outlines a recommended schedule and a step-by-step checklist for performing the repository history rewrite. It is intended for maintainers who will run the final rewrite and force-push to `origin` after preview validation and sign-off.

Suggested maintenance window
----------------------------
- Duration: 60 minutes (includes backup, rewrite, validation, and rollback window)
- Recommended start: pick an off-peak time for contributors (e.g., 02:00 UTC)
- Notify: Post the final announcement in the repo PR and maintainer channel at least 48 hours prior.

Pre-requisites (before window)
------------------------------
1. All non-destructive commits containing docs and scripts are pushed (done).
2. Preview tarball(s) have been validated by at least one maintainer (smoke checks done).
3. A backup mirror tarball is created and uploaded to the chosen artifact store (or attached to the PR). Keep the backup until the rewrite is verified.
4. `git-filter-repo` is available on the maintainer machine or CI runner. If system installation is restricted, create a temporary venv and `pip install git-filter-repo`.

Checklist (run during the maintenance window)
-------------------------------------------
1. Create a fresh mirror (from an authorized machine):

   git clone --mirror https://github.com/TaintedHorizon/Python_Testing_Vibe.git repo-rewrite.git

2. Create a backup tarball of the fresh mirror and upload it to the artifact store. Verify SHA256 and retain the backup until verification complete.

   tar -czf repo-backup-$(date -u +%Y%m%dT%H%M%SZ).tar.gz repo-rewrite.git
   sha256sum repo-backup-*.tar.gz

3. Run `git-filter-repo` with the paths to remove. Example:

   # place the list of paths into `rewrite-paths.txt` (one path per line)
   git -C repo-rewrite.git filter-repo --paths-from-file ../rewrite-paths.txt --force

4. Inspect the rewritten mirror locally for unexpected deletions.

5. Create a working checkout and run the full validation suite (smoke + CI consumer validation). Recommended runner: GitHub Actions self-hosted or a runner with Python 3.11 for wheelhouse consumer checks.

6. If validation passes, push rewritten refs to origin (force push) and tags:

   cd repo-rewrite.git
   git push --force --tags origin 'refs/heads/*:refs/heads/*'

7. Post a status update to the PR and maintainer channel including backup SHA, preview SHA, and the time of the force-push.

Rollback (if needed)
---------------------
- Use the backup tarball to restore refs. For emergencies, open a GitHub support ticket and attach the backup tarball and SHA.

Contact
-------
- Primary: @TaintedHorizon
- Secondary: repo maintainers (see CODEOWNERS)

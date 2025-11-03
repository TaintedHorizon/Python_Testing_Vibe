# History Rewrite: Push Plan & Checklist

This document is a maintainer-facing plan to safely push a rewritten repository mirror to
`origin`. It assumes you have already created and validated a preview tarball produced by
`scripts/repo/make_rewrite_preview.sh` and that you have a trusted backup tarball of the
original mirror.

Top-level summary
- Preview tarball (local): `ci_artifacts/repo-rewrite-preview-local-force-20251030T002051Z.tar.gz`
  - SHA256: `2f1674f108f8fd21a8e038864ff2cbc32d06899986fc2dfd79ffa68538801ffb`
  - Size: ~120 MB

High-level intent
- Remove large or sensitive historical objects tracked in HEAD/history (examples used during
  the preview: `doc_processor/venv`, `repo-rewrite.git`, `ci_artifacts`, `ui_tests/node_modules`).
- Keep a verified preview and backup(s). Do not push anything to `origin` without maintainer
  coordination and a recovery plan.

Prerequisites (local machine / maintainer runbox)
- `git`, `git-filter-repo` installed (or use a temporary venv: `python -m venv /tmp/gfr && /tmp/gfr/bin/pip install git-filter-repo`).
- Sufficient disk space for a mirror clone and backups.
- Coordinated maintainer window with write privileges for required branches.

Checklist — verification before pushing
1. Verify preview tarball checksum locally:

   ```bash
   sha256sum ci_artifacts/repo-rewrite-preview-local-force-20251030T002051Z.tar.gz
   # expect: 2f1674f108f8fd21a8e038864ff2cbc32d06899986fc2dfd79ffa68538801ffb
   ```

2. Extract and inspect the rewritten mirror and run a test checkout:

   ```bash
   mkdir /tmp/rewrite_verify && tar -xzf ci_artifacts/repo-rewrite-preview-local-force-20251030T002051Z.tar.gz -C /tmp/rewrite_verify
   git clone /tmp/rewrite_verify/repo-mirror.git /tmp/rewrite_verify/checkout
   # run lightweight smoke tests from the checkout (or your normal test matrix)
   cd /tmp/rewrite_verify/checkout
   /path/to/project/doc_processor/venv/bin/python -m pytest -q doc_processor/tests/e2e/test_health.py doc_processor/tests/e2e/test_root_content.py
   ```

3. Confirm the removed paths/blobs are not present:

   ```bash
   # from the mirror directory
   git -C /tmp/rewrite_verify/repo-mirror.git rev-list --objects --all | grep -E "(venv|node_modules|ci_artifacts)" || true
   ```

4. Identify branches/tags that might reference removed objects and decide how to handle them.

5. Create an additional offline backup of the current remote state (recommended):

   ```bash
   mkdir /tmp/orig-backup
   git clone --mirror https://github.com/TaintedHorizon/Python_Testing_Vibe.git /tmp/orig-backup/repo-mirror.git
   tar -C /tmp/orig-backup -czf ci_artifacts/repo-mirror-orig-$(date -u +%Y%m%dT%H%M%SZ).tar.gz repo-mirror.git
   ```

Push plan (preview -> preview-remote -> origin) — one maintainer pushes each step
1. Push rewritten mirror to a preview remote (do not touch origin yet):

   ```bash
   # create a temporary remote on GitHub (e.g. a personal fork or 'preview' remote you control)
   git -C /tmp/rewrite_verify/repo-mirror.git remote add preview https://github.com/<ORG_OR_USER>/Python_Testing_Vibe-preview.git
   git -C /tmp/rewrite_verify/repo-mirror.git push --mirror preview
   ```

2. Signal the team: open a short PR or issue referencing the preview remote and provide the
   preview tarball SHA + link, and a summary of what's been removed.

3. If the preview remote and test checkout pass full verification, plan the timed force-push
   to `origin` with the following commands (to be executed by an authorized maintainer):

   ```bash
   # from the rewritten mirror (local copy you've verified)
   git -C /tmp/rewrite_verify/repo-mirror.git remote add origin https://github.com/TaintedHorizon/Python_Testing_Vibe.git
   # push everything forcefully
   git -C /tmp/rewrite_verify/repo-mirror.git push --force --all origin
   git -C /tmp/rewrite_verify/repo-mirror.git push --force --tags origin
   ```

4. Immediately after the push, run a minimal verification in a fresh clone:

   ```bash
   git clone https://github.com/TaintedHorizon/Python_Testing_Vibe.git /tmp/postrewrite
   cd /tmp/postrewrite
   # run smoke tests or CI smoke workflow locally
   /path/to/project/doc_processor/venv/bin/python -m pytest -q doc_processor/tests/e2e/test_health.py
   ```

Rollback/Recovery plan
- If anything goes wrong, restore from the offline backup tarball created earlier (push back the original mirror):

  ```bash
  tar -xzf ci_artifacts/repo-mirror-orig-<TIMESTAMP>.tar.gz -C /tmp
  git -C /tmp/repo-mirror.git push --force --all origin
  git -C /tmp/repo-mirror.git push --force --tags origin
  ```

Communication & coordination
- Announce the planned force-push window to all active contributors and maintainers.
- Ask active PR authors to pause merges and rebase after the force-push.
- Provide the preview tarball SHA and the backup SHA in the announcement message.

Notes & caveats
- The preview tarball produced with a `--force` git-filter-repo run contains local commits and the
  expected removals; it is essential to thoroughly test the preview before any push.
- Branch refs outside `refs/remotes/` may need manual deletion as noted by git-filter-repo.
- This process rewrites history; coordinate with GitHub admins if the repository has branch protection rules.

Contact
- If you want, I can (A) produce a short PR text for the maintainer announcement, and (B) create a one-click checklist file that maintainers can follow during the push window.

---
Generated by the repo automation during the `feature/inline-manylinux` work. Use with care.

# Final: History Rewrite Announcement (ready-to-send)

This is the final announcement and call-to-action for maintainers to approve and run the repository history rewrite. It is intentionally prescriptive and contains exact commands, preview SHA, backup instructions, and a proposed maintenance window.

Summary
-------
- Purpose: Remove local-only large artifacts and mirrors (e.g., `repo-rewrite.git/`, `ci_artifacts/`, `doc_processor/venv/`, `ui_tests/node_modules/`) from history to shrink repository size and enforce best-practices.
- Branch: `feature/inline-manylinux` — contains non-destructive prep commits (docs, scripts, CI wiring).
- Preview tarball: `ci_artifacts/repo-rewrite-preview-local-force-20251030T002051Z.tar.gz`
  - SHA256: `2f1674f108f8fd21a8e038864ff2cbc32d06899986fc2dfd79ffa68538801ffb`

Why we must do this now
-----------------------
- Large local artifacts are inflating clone and CI times and hide true repository contents.
- CI and wheelhouse provenance are now in place to ensure reproducibility of heavy-deps builds.
- The rewrite is safe if performed with the backup and validation steps below; we've prepared preview artifacts and smoke validation to reduce risk.

Required pre-approvals
----------------------
- One maintainer must reply to this announcement in the PR or maintainer channel with an explicit approval comment containing the words: "I approve the rewrite and backup SHA <backup-sha>".
- A second maintainer must acknowledge the time-window and volunteer to act as rollback contact.

Proposed maintenance window
---------------------------
- Duration: 60 minutes
- Suggested start: pick an off-peak time (e.g., 02:00 UTC). If that's fine, reply with preferred date/time.

Backup creation (must be performed before any destructive push)
--------------------------------------------------------------
Run these commands locally (or in a trusted runner) to create and upload a backup mirror tarball:

```bash
# 1. Create a fresh mirror clone
git clone --mirror https://github.com/TaintedHorizon/Python_Testing_Vibe.git repo-rewrite.git

# 2. Create backup tarball
tar -czf repo-backup-$(date -u +%Y%m%dT%H%M%SZ).tar.gz repo-rewrite.git

# 3. Compute SHA256 and keep it recorded
sha256sum repo-backup-*.tar.gz
```

Upload the resulting tarball to the chosen artifact store (S3/GCS/GitHub Releases). If you want me to upload from CI, configure the appropriate CI secrets and I'll wire it into the workflow — see `scripts/ci/upload_artifacts_optin.sh`.

Exact rewrite commands (maintainer-run; dry-run-able)
----------------------------------------------------
1. Prepare the paths to remove in `rewrite-paths.txt`, one per line, for example:

```
repo-rewrite.git/
ci_artifacts/
doc_processor/venv/
ui_tests/node_modules/
```

2. Create a fresh mirror and run git-filter-repo (dry-run by inspecting the output and counts):

```bash
git clone --mirror https://github.com/TaintedHorizon/Python_Testing_Vibe.git repo-rewrite.git
git -C repo-rewrite.git filter-repo --paths-from-file ../rewrite-paths.txt --force
```

3. Inspect the rewritten mirror, create a working checkout and run validation:

```bash
git clone repo-rewrite.git /tmp/rewrite-checkout
cd /tmp/rewrite-checkout
# Run the smoke tests (or full test matrix in CI)
PLAYWRIGHT_E2E=1 E2E_URL=http://127.0.0.1:5000/ doc_processor/venv/bin/python -m pytest doc_processor/tests/e2e/test_health.py doc_processor/tests/e2e/test_root_content.py -q
```

4. If validation passes, push rewritten refs and tags to origin (force push):

```bash
cd repo-rewrite.git
git push --force --tags origin 'refs/heads/*:refs/heads/*'
```

Rollback instructions
---------------------
- If anything goes wrong, restore refs using the backup mirror tarball (unpack and push refs back), or contact GitHub Support with the backup tarball attached.

Sign-off checklist (to be completed by maintainers before step 4)
-----------------------------------------------------------------
1. Backup tarball created and SHA recorded and uploaded.
2. Preview tarball SHA validated by at least one maintainer (smoke tests passed). Preview SHA above.
3. At least two maintainers explicitly approve in the PR comments.
4. A maintainer responsible for rollback is identified and available during the window.

How to approve now
-------------------
- Copy this message into the PR or maintainer channel and reply with: "APPROVED: ready for rewrite — backup SHA: <sha> — scheduled <date/time> UTC". The presence of that explicit comment from one maintainer plus an ACK from a second maintainer is required.

Questions or help
-----------------
- If you want me to handle the backup upload to S3/GCS/GH Releases, tell me which provider and provide the CI secret names (I can then wire `scripts/ci/upload_artifacts_optin.sh` into CI to do the upload from the runner). I will not perform the destructive push without explicit approval comments as described above.

---
Ready to post. If you confirm, I'll (1) create a GitHub Issue or post to the PR body with this message (if you want me to do that, provide permission), or (2) leave this file in the repo for you to copy/paste. Which do you prefer? 

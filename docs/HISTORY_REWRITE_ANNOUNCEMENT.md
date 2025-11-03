# Draft: History Rewrite Announcement

This is a draft maintainer announcement for the proposed history-rewrite on branch `feature/inline-manylinux`.

Summary
-------
- Purpose: Remove large/co-mingled artifacts and improve CI determinism by excluding ephemeral build artifacts and local mirrors from history. The rewrite is limited to removing the following paths from past commits: `repo-rewrite.git/`, `ci_artifacts/`, `doc_processor/venv/`, `ui_tests/node_modules/`, and any other large local-only files discovered during review.
- Branch: `feature/inline-manylinux` (already pushed with non-destructive commits: docs + scripts)

Preview artifacts
-----------------
- Preview tarball (local force-run): ci_artifacts/repo-rewrite-preview-local-force-20251030T002051Z.tar.gz
  - SHA256: 2f1674f108f8fd21a8e038864ff2cbc32d06899986fc2dfd79ffa68538801ffb

Backups
-------
- Before performing any force-push we will create and publish a backup of the current repository state (bare mirror + packfiles). The backup tarball will be attached to the maintainer review and stored in the CI artifact bucket (or provided as a downloadable link). Keep the backup until the rewrite is verified.

Planned rewrite commands (for maintainers)
-----------------------------------------
These are the canonical commands we will run locally from a maintainer machine or CI runner with `git-filter-repo` available. Replace `<mirror-path>` and `<rewrite-paths-file>` as needed.

1. Create a fresh mirror clone:

   git clone --mirror https://github.com/TaintedHorizon/Python_Testing_Vibe.git repo-rewrite.git

2. Run `git-filter-repo` (dry-run or preview mode if available):

   # Example: remove listed paths from history
   git -C repo-rewrite.git filter-repo --paths-from-file ../rewrite-paths.txt --force

3. Inspect the rewritten mirror and run the validation test matrix on a checkout of the rewritten repo.

4. Push the rewritten history (force push):

   cd repo-rewrite.git
   git push --force --tags origin 'refs/heads/*:refs/heads/*'

Rollback
--------
- If anything goes wrong, restore from the backup mirror/tarball by replacing refs on the remote with the backed-up mirror or contact GitHub support for assistance.
- Keep the backup tarball SHA handy and verify checksums before any destructive update.

Validation & smoke checks (required before push)
-----------------------------------------------
1. Run the smoke test suite (pytest smoke and the two deterministic e2e checks: `doc_processor/tests/e2e/test_health.py` and `doc_processor/tests/e2e/test_root_content.py`) on a checkout of the rewritten repo.
2. Confirm wheelhouse consumer tests (if applicable) by running the CI consumer validation step locally or on the runner.

Schedule & communication
------------------------
- Target a maintenance window where contributors are aware. Provide at least 48h notice if possible.
- Post this draft to the maintainer channel and the PR conversation with the preview SHA and the backup SHA attached.

Contact
-------
- Primary: @TaintedHorizon
- Secondary: repository maintainers (see CODEOWNERS)

---
This is a draft — please review the text above and the preview tarball. After approval I will finalize the announcement, run the final validation suite, and coordinate the force-push step.

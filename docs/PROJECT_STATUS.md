# Project Status — October 30, 2025

This file is a concise single-source-of-truth snapshot for the three primary goals agreed for the repository.

Overall progress (by goal):

- Goal A — CI: Make GitHub Actions green — 75% complete
- Goal B — Repo cleanup (history rewrite & best-practices) — 65% complete
- Goal C — Doc processor E2E testability — 80% complete

Key artifacts & locations
- Preview tarball (local force-run): `ci_artifacts/repo-rewrite-preview-local-force-20251030T002051Z.tar.gz`
  - SHA256: `2f1674f108f8fd21a8e038864ff2cbc32d06899986fc2dfd79ffa68538801ffb`
- Validation summary: `docs/ci-archive/repo-rewrite-preview-local-force-20251030T002051Z-validation.md`
- Draft announcement: `docs/HISTORY_REWRITE_ANNOUNCEMENT.md`
- Push plan: `scripts/repo/PUSH_PLAN.md`

Immediate next actions (short list)
1. Decide external storage for backup tarball (S3/GCS/GH Releases). Provide CI secret names if you want optional uploads enabled.
2. Obtain final maintainer approval to perform the rewrite. Follow `docs/HISTORY_REWRITE_SCHEDULE.md` checklist during the window.
3. Run a full CI/runner validation of the rewritten checkout (including wheelhouse consumer validation) prior to force-push.

How this file is maintained
- This file is intentionally lightweight. I can update it automatically from the in-chat todo list when requested, or you can update it manually. When the rewrite is performed, update the percentages and record the rewritten HEAD SHAs here.

Contact
- Primary: @TaintedHorizon

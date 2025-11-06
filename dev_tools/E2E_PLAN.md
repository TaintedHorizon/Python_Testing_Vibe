# E2E Smoke & Stabilization Plan

Goal: make it straightforward to run a lightweight E2E smoke locally and in CI so Playwright tests are reliable.

Short-term plan (small increments):

1. Smoke harness
   - Provide a quick `dev_tools/run_e2e_smoke.sh` script that:
     - Activates `doc_processor/venv` (instructions in repo README)
     - Runs `./start_app.sh` in background
     - Waits for readiness probe and runs a single Playwright smoke test (e.g., open intake page and assert status)
2. CI integration
   - Add a small `ci-smoke.yml` job already present; update it to run the smoke harness only when the `e2e` label is present or as a manual step.
3. Flakiness triage
   - Capture screenshots and logs on failures and upload as artifacts.
4. Metrics
   - Track pass/fail rate across runs for the smoke job for 14 days to identify flakiness.

Local commands (developer):

```bash
# from repo root
cd doc_processor
source venv/bin/activate
# start background app
../start_app.sh &
# run the smoke harness
bash ../dev_tools/run_e2e_smoke.sh
```

Acceptance criteria:
- The smoke harness completes in < 2 minutes on CI VM.
- Playwright smoke passes reliably on 90% runs for 7 days before expanding tests.


# Playwright E2E — Local Reproduction Guide

This document lists the exact commands to reproduce the Playwright E2E environment locally in a safe, repeatable way.

Quick notes:
- Use the `Makefile` targets provided at the repo root for single-spec and full-run flows:
  - `make e2e-single` — runs a single Node Playwright spec (fast).
  - `make e2e-full` — runs the full local reproduction script (`./scripts/run_local_e2e.sh`) with safe DB overrides.

1) Fast: run a single Node Playwright spec (no Flask app needed)

```bash
cd /path/to/repo
make e2e-single
```

This runs `ui_tests`'s e2e spec `intake_progress.spec.js`. It will run `npm ci` in `ui_tests` if needed.

2) Full reproducible run (starts Flask app, runs Playwright tests)

The full run will create/activate the Python venv, install Python and Node dependencies, start the Flask app, wait for the health check, and run the Node Playwright test runner. It also forwards safe DB overrides to avoid touching production.

```bash
cd /path/to/repo
make e2e-full
```

Notes and tips:
- If Playwright browser install fails you may need system packages on Linux. On Ubuntu/Debian run:

```bash
sudo apt-get update
sudo apt-get install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxss1 libgbm1 libxcomposite1 libxrandr2 libasound2 curl
```

- The `e2e-full` target sets `DATABASE_PATH` and `DB_BACKUP_DIR` to repo-local paths to avoid accidental writes to any production locations.
- To debug failures, inspect artifacts in `doc_processor/tests/e2e/artifacts/`.

Recommended environment variables for troubleshooting (optional):

```bash
# Faster tests (skip heavy OCR/LLM)
export FAST_TEST_MODE=1
# Avoid calling external LLM
export SKIP_OLLAMA=1
# Gate Playwright tests
export PLAYWRIGHT_E2E=1
```

If you'd like me to also apply the same safe DB overrides to the CI workflow (`.github/workflows/playwright-e2e.yml`), say "apply CI override" and I'll patch the workflow.
# Running Playwright E2E locally (safe, reproducible)

This document shows the exact commands to run Playwright E2E tests locally in two modes:

- Fast single-spec run (no Flask app required)
- Full local reproduction (starts the Flask app, runs Playwright tests)

Note: These commands intentionally override `DATABASE_PATH` and `DB_BACKUP_DIR` to repo-local paths to avoid touching any external or production databases.

Prerequisites
- Node (for Playwright Node runner)
- npm
- Python 3.12
- The project repo checked out and at the repo root

1) Single-spec (fast)

Install Node deps once:

```bash
cd ui_tests
npm ci
cd ..
```

Run the single Node Playwright spec (fast, no server required):

```bash
cd ui_tests
npx playwright test e2e/intake_progress.spec.js --reporter=list
```

2) Full local E2E (recommended for reproducing CI)

This runs `./scripts/run_local_e2e.sh` and will:

- create/activate `doc_processor/venv` (if missing)
- install Python and Node deps
- install Playwright browsers (may require apt packages)
- start the Flask app using `./start_app.sh`
- run Playwright tests in `ui_tests`

Run the full script with safe overrides:

```bash
# from repo root
DATABASE_PATH=$$(pwd)/doc_processor/documents.db \
DB_BACKUP_DIR=$$(pwd)/doc_processor/db_backups \
FAST_TEST_MODE=1 SKIP_OLLAMA=1 PLAYWRIGHT_E2E=1 ./scripts/run_local_e2e.sh
```

Makefile targets

You can use the included Makefile from the repo root:

```bash
make e2e-single   # run the single Playwright spec
make e2e-full     # run the full local reproduction (installs deps, starts app, runs tests)
make e2e-setup    # prepare venv and install deps
```

Troubleshooting
- If Playwright browser install fails on Linux, run:

```bash
doc_processor/venv/bin/python -m playwright install --with-deps
# or, install system packages on Ubuntu/Debian:
sudo apt-get update && sudo apt-get install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxss1 libgbm1 libxcomposite1 libxrandr2 libasound2 curl
```

- Ensure the `doc_processor/venv` virtual environment is created and activated before running Python-based steps.

Safety note
- The CI workflow and these local commands intentionally set `DATABASE_PATH` and `DB_BACKUP_DIR` to repo-local paths to avoid accidental writes to production locations like `/home/svc-scan/db`.

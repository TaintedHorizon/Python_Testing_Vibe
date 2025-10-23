# Smoke test helper

This repository includes a lightweight smoke script to verify that the non-E2E test subset runs under a test-scoped environment (so test writes are redirected to safe locations).

How to run locally

1. From the repo root, make sure you have Python 3 and virtualenv available.
2. Run the smoke script (it will create/use `doc_processor/venv`):

```bash
bash ci/smoke.sh
```

What it does

- Exports `TEST_TMPDIR` (defaults to `/tmp/python_testing_vibe_tests`).
- Sources `doc_processor/.env.test` when present.
- Creates/uses a venv at `doc_processor/venv` and installs `doc_processor/requirements.txt` (or at least `pytest`).
- Runs `pytest -q -k "not e2e and not playwright"`.

Notes

- The script is intentionally lightweight and intended for local developer runs. A manual GitHub Actions workflow is included to allow maintainers to run the same check on-demand.
- If you want an always-on CI check, we can add a constrained workflow with path filters; tell me and I will add one.

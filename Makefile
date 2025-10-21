## Makefile - helper targets for running E2E locally

.PHONY: e2e-single e2e-full e2e-setup

# Run a single Node Playwright spec (fast; does not start Flask app)
e2e-single:
	@echo "Running single Playwright spec (ui_tests/e2e/intake_progress.spec.js)"
	@(cd ui_tests && npm ci)
	@(cd ui_tests && npx playwright test e2e/intake_progress.spec.js --reporter=list)

# Run the full local reproduction script (creates venv, installs deps, starts app, runs tests)
e2e-full:
	@echo "Running full local E2E (this may install Playwright browsers and Node deps)"
	# We forward safe overrides for DB paths to avoid touching production data.
	DATABASE_PATH=$$(pwd)/doc_processor/documents.db \
	DB_BACKUP_DIR=$$(pwd)/doc_processor/db_backups \
	FAST_TEST_MODE=1 SKIP_OLLAMA=1 PLAYWRIGHT_E2E=1 ./scripts/run_local_e2e.sh

e2e-setup:
	@echo "Prepare Python and Node dependencies for E2E"
	python3 -m venv doc_processor/venv || true
	. doc_processor/venv/bin/activate && pip install -r doc_processor/requirements.txt && pip install playwright pytest-playwright
	(cd ui_tests && npm ci)

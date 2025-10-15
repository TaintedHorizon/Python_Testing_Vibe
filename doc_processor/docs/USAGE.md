# Usage Guide for doc_processor

> For a full architectural breakdown and layer responsibilities, see `../../ARCHITECTURE.md`. For a high-level file map, see the Comprehensive File Map section in the root `README.md`.

## Quick Start

1. Install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Set up your `.env` file (see `.env.sample`).
3. Initialize the database:
   ```bash
   python dev_tools/database_setup.py
   ```
4. Start the Flask server:
   ```bash
   python -m doc_processor.app
   ```
5. Access the web UI at [http://localhost:5000](http://localhost:5000)

## Workflow
- Place PDFs in your configured INTAKE_DIR.
- Use the Batch Control UI to process, verify, group, and export documents.
- All status and progress is tracked in the SQLite database.

## AI Configuration & Tuning

### Context Window Monitoring
The system automatically logs AI context usage for each task:
```bash
[LLM DETECTION] Context: 750~tokens/2048 (36.6% usage)
[LLM CATEGORY] Context: 1200~tokens/2048 (58.6% usage)
```

### Performance Tuning
- **80%+ usage**: Consider increasing context window in `.env`
- **95%+ usage**: Context likely truncated - increase immediately
- **Overflow warning**: Response quality will be degraded

### Context Window Settings
Adjust these in your `.env` file based on monitoring logs:
```bash
OLLAMA_CTX_CLASSIFICATION=2048    # Simple classification tasks
OLLAMA_CTX_DETECTION=2048         # Document structure analysis
OLLAMA_CTX_CATEGORY=2048          # Category assignment
OLLAMA_CTX_ORDERING=2048          # Page ordering
OLLAMA_CTX_TITLE_GENERATION=4096  # Document naming (needs more context)
```

## Troubleshooting
Need to understand where a function or route lives? Consult:
- `ARCHITECTURE.md` (layer overview & dependency flow)
- Root `README.md` (high-level file map table)
- `doc_processor/readme.md` (internal module quick reference)
- Set `DEBUG_SKIP_OCR=true` in `.env` to bypass OCR for testing.
- Use scripts in `dev_tools/` for database resets and diagnostics.
- Check logs for errors and review the database for stuck batches.
- Monitor AI context usage logs to optimize performance vs quality.

## Avoid running the Flask development server during tests

Sometimes you'll see "Starting Flask development server" lines in `app.log` or your terminal. Those appear when someone starts the long-lived dev server (for example by running `python -m doc_processor.app` directly) rather than using the provided startup script or the Flask test client. During automated tests you should avoid launching a persistent server — the test harness uses the Flask test client and starts the app in-process.

Recommendations:

- For manual development runs, always use the repository startup script which configures the correct virtualenv and environment:

```bash
./start_app.sh
```

- For automated tests, run pytest (the harness uses the Flask test client). Do not run `python -m doc_processor.app` in CI or test runs.

- If you need to run the app manually for debugging, prefer doing so in a separate terminal and stop it before running the test suite to avoid port conflicts and noisy logs.

These practices prevent accidental background servers from interfering with tests and keep logs clean.

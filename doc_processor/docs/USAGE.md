# Usage Guide for doc_processor

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
- Use the Mission Control UI to process, verify, group, and export documents.
- All status and progress is tracked in the SQLite database.

## Troubleshooting
- Set `DEBUG_SKIP_OCR=true` in `.env` to bypass OCR for testing.
- Use scripts in `dev_tools/` for database resets and diagnostics.
- Check logs for errors and review the database for stuck batches.

This folder contains archived manual diagnostic and demo scripts previously
located in `doc_processor/dev_tools/` and renamed to avoid pytest auto-collection.

Guidance:
- These are manual tools for developer debugging and are not intended for CI.
- Run them from the repo root with the project venv activated.

Examples:
- `detection_manual.py` - filename heuristics and optional intake analysis
- `flask_context_manual.py` - checks SSE route for context issues
- `progress_tracking_manual.py` - runs progress generator printing events

If you want to promote any of these to CI tests, convert noisy I/O paths to
fixtures and add deterministic assertions under `doc_processor/tests/`.

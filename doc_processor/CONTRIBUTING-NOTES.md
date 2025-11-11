Repository contribution pointers
--------------------------------

This small file points to repository-level contributing guidance relevant to the `doc_processor` package.

- Repository archival/backups guidance: `.github/CONTRIBUTING-ARCHIVES.md`
- Project-level contributor summary: `docs/CONTRIBUTING-README.md`

If you're contributing runtime changes (routes, processing, DB changes), follow `doc_processor/CONTRIBUTING.md` and add tests where practical.

Note: For fast local test runs you can set `FAST_TEST_MODE=1` to skip heavy binary deps (OCR, PyMuPDF, etc.). Install full heavy requirements from `requirements-heavy.txt` when you need to run full tests or debug OCR-related features.

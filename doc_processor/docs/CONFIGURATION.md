# Configuration Reference

This document lists all supported environment variables read by `config_manager.AppConfig` and their effects. Copy `.env.sample` to `.env` and adjust.

| Variable | Default | Description |
|----------|---------|-------------|
| ARCHIVE_RETENTION_DAYS | 30 | Days to retain items in archive directory before cleanup tools may purge. |
| DATABASE_PATH | documents.db | SQLite database path (absolute recommended). |
| INTAKE_DIR | intake | Directory for incoming source files. |
| PROCESSED_DIR | processed | Working directory for batch/page intermediates. |
| WIP_DIR | (PROCESSED_DIR) | Backwards compatibility alias; normally same as PROCESSED_DIR. |
| ARCHIVE_DIR | archive | Future archival store (optional currently). |
| FILING_CABINET_DIR | filing_cabinet | Final categorized export destination. |
| NORMALIZED_DIR | normalized | Cross-run cache of normalized PDFs (image→PDF). |
| NORMALIZED_CACHE_MAX_AGE_DAYS | 14 | Age threshold for background GC of normalized cache. |
| OLLAMA_HOST | (none) | URL of local Ollama server. |
| OLLAMA_MODEL | (none) | Model name/tag to use for LLM tasks. |
| OLLAMA_CONTEXT_WINDOW | 8192 | Global default context window size. |
| OLLAMA_TIMEOUT | 45 | Seconds before LLM request times out. |
| OLLAMA_NUM_GPU | (none) | GPU count hint for Ollama (optional). |
| OLLAMA_CTX_CLASSIFICATION | 2048 | Context window for classification task. |
| OLLAMA_CTX_DETECTION | 2048 | Context window for detection (single vs batch). |
| OLLAMA_CTX_CATEGORY | 2048 | Context window for per-page category assignment. |
| OLLAMA_CTX_ORDERING | 2048 | Context window for ordering tasks. |
| OLLAMA_CTX_TITLE_GENERATION | 4096 | Context window for filename/title generation. |
| LOG_FILE_PATH | logs/app.log | Main log file path. |
| LOG_MAX_BYTES | 10485760 | Size threshold for rotating log file. |
| LOG_BACKUP_COUNT | 5 | Number of rotated log backups to retain. |
| LOG_LEVEL | INFO | Logging verbosity (INFO/DEBUG/WARNING/ERROR). |
| DEBUG_SKIP_OCR | false | Skip heavy OCR in certain code paths (legacy flag). |
| ENABLE_TAG_EXTRACTION | true | Perform LLM tag extraction during export (adds latency). |
| FAST_TEST_MODE | false | Bypass heavy OCR/LLM in tests; creates fallback searchable PDFs. |
| RESCAN_OCR_DPI | 180 | DPI for manual rescan OCR rendering. |
| OCR_RENDER_SCALE | 2.0 | Scale factor for PDF rasterization (2.0 ≈ 144 DPI). |
| OCR_OVERLAY_TEXT_LIMIT | 2000 | Truncation limit for invisible per-page OCR overlay text. |

## Derived / Internal
Status constants (e.g., `STATUS_PENDING_VERIFICATION`) are not configurable; they are loaded into the config object for consistency.

## Adding a New Variable
1. Add dataclass field with default in `config_manager.py`.
2. Load via `get_env`/`get_optional_env` inside `load_from_env`.
3. Update `.env.sample` and this document.
4. Reference via `from config_manager import app_config` (never `import os` inline in core code).

## Minimal .env for Single Export Testing
```
INTAKE_DIR=/absolute/path/to/intake
PROCESSED_DIR=/absolute/path/to/processed
FILING_CABINET_DIR=/absolute/path/to/filing_cabinet
DATABASE_PATH=/absolute/path/to/documents.db
FAST_TEST_MODE=true
ENABLE_TAG_EXTRACTION=false
OCR_RENDER_SCALE=1.5
OCR_OVERLAY_TEXT_LIMIT=1500
```

## Performance Tuning Tips
- Reduce `OCR_RENDER_SCALE` to 1.0 for faster test cycles (lower OCR fidelity).
- Increase `OCR_OVERLAY_TEXT_LIMIT` only if downstream search requires longer contiguous text blocks.
- Disable `ENABLE_TAG_EXTRACTION` to speed up export when tags not needed.
- Use `FAST_TEST_MODE=true` in CI for deterministic tests without OCR variance.

## Cache & Invalidation
Searchable PDF OCR caching now includes a file signature (size + mtime + SHA1 of first 64KB) stored in `ocr_source_signature` column when available. If the source file changes, the cache is invalidated automatically.

---
Updated: 2025-10-07

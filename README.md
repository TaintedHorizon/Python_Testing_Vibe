
# Python_Testing_Vibe

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A multi-purpose development repository containing various Python projects and utilities, with a focus on document processing and system administration tools.

## Repository Structure

### 📁 Comprehensive File Map (High-Level)
This map lists active, support, legacy, and runtime directories/files for fast orientation.

| Path | Type | Purpose |
|------|------|---------|
| `start_app.sh` | Script | Canonical launcher: activates venv + runs module entrypoint |
| `validate_environment.py` | Script | (Planned) Environment validation helper (currently light/placeholder) |
| `doc_processor/app.py` | Core | Flask application entrypoint (Blueprint registration & global setup) |
| `doc_processor/config_manager.py` | Core | Central configuration loader & typed config object |
| `doc_processor/database.py` | Core | SQLite access helpers + connection context manager |
| `doc_processor/db_utils.py` | Support | Supplemental DB utilities/migrations |
| `doc_processor/processing.py` | Core | OCR, AI, normalization cache, rotation, export helpers |
| `doc_processor/document_detector.py` | Core | Intake document & image analysis + normalization pipeline |
| `doc_processor/llm_utils.py` | Core | Ollama / LLM interaction helpers |
| `doc_processor/security.py` | Support | Filename & path sanitization helpers |
| `doc_processor/exceptions.py` | Support | Custom exception classes |
| `doc_processor/batch_guard.py` | Support | Prevent phantom/duplicate batch creation |
| `doc_processor/utils/helpers.py` | Support | General shared helper functions |
| `doc_processor/routes/` | Package | Flask Blueprints (segmented route handlers) |
| `doc_processor/routes/intake.py` | Route | Intake analysis, rotation save, initial AI classification |
| `doc_processor/routes/batch.py` | Route | Batch control, smart processing orchestration (SSE + cancel) |
| `doc_processor/routes/manipulation.py` | Route | Verification, grouping, ordering workflows |
| `doc_processor/routes/export.py` | Route | Export & finalization, file serving, PDF viewer endpoints |
| `doc_processor/routes/admin.py` | Route | System / maintenance endpoints |
| `doc_processor/routes/api.py` | Route | Lightweight AJAX/REST auxiliary endpoints |
| `doc_processor/services/` | Package | Business logic layer modules |
| `doc_processor/services/document_service.py` | Service | Document-centric operations |
| `doc_processor/services/batch_service.py` | Service | Batch orchestration & state transitions |
| `doc_processor/services/export_service.py` | Service | Export assembly & finalization |
| `doc_processor/templates/` | Templates | All Jinja2 UI templates |
| `doc_processor/templates/pdf_viewer.html` | Template | Embedded local PDF.js viewer |
| `doc_processor/static/pdfjs/` | Assets | Vendored PDF.js (offline, deterministic) |
| `doc_processor/intake/` | Runtime Dir | User-provided source files awaiting processing |
| `doc_processor/processed/` | Runtime Dir | Batch working directory (intermediate state) |
| `doc_processor/filing_cabinet/` | Runtime Dir | Final exported documents (categorized) |
| `doc_processor/archive/` | Runtime Dir | (Currently unused) Potential archival store |
| `normalized/` | Runtime Dir | Global normalized (image→PDF) hash cache (outside package) |
| `doc_processor/logs/` | Runtime Dir | Application logs (e.g., app.log) |
| `doc_processor/instance/` | Runtime Dir | Flask instance artifacts |
| `doc_processor/documents.db` | Data | Primary SQLite database (git-ignored) |
| `doc_processor/dev_tools/` | Tools | Admin & maintenance scripts (DB, cleanup, diagnostics) |
| `doc_processor/tests/` | Tests | Pytest tests for processor modules |
| `tests/` | Tests | Root-level tests (broader or integration) |
| `doc_processor/test_complete_workflow.py` | Script/Test | Manual/integration workflow runner |
| `doc_processor/test_pdf_conversion.py` | Script/Test | Conversion / OCR path validation |
| `doc_processor/CHANGELOG.md` | Docs | Chronological change log |
| `doc_processor/CONTRIBUTING.md` | Docs | Contribution guidelines (processor scope) |
| `doc_processor/docs/USAGE.md` | Docs | Detailed usage instructions |
| `doc_processor/docs/README.md` | Docs | Documentation index (deep dives) |
| `doc_processor/docs/LEGACY_CODE.md` | Docs | Legacy naming & deprecation policy |
| `.github/copilot-instructions.md` | Docs | AI assistant operational guardrails |
| `COPILOT_QUICK_REFERENCE.md` | Docs | Quick assistant reference (consider merging) |
| `README.md` | Docs | Repository overview & quick start |
| `doc_processor/readme.md` | Docs | In-depth processor documentation |
| `LICENSE` | Legal | MIT License (root) |
| `doc_processor/requirements.txt` | Dependencies | Processor dependencies list |
| `Document_Scanner_Gemini_outdated/` | Legacy | Deprecated Gemini-based scanner (archive only) |
| `Document_Scanner_Ollama_outdated/` | Legacy | Deprecated early Ollama implementation (archive only) |
| `tools/` | Misc Tools | Independent utility sub-projects |

Legend: Core = essential runtime; Support = ancillary active; Legacy = historical only; Runtime Dir = generated/working; Service/Route/Template = layered architecture components.

> Cleanup candidates after stability window: unused `archive/` dir (after confirming no workflow dependency).

### 🏠 Main Projects

#### **`doc_processor/`** - Human-in-the-Loop Document Processing System
Production-ready document processing pipeline with AI integration, human verification, and complete audit trails.

**🎉 MAJOR ARCHITECTURE UPDATE (October 2025):**
- **Completely refactored from monolithic to modular architecture**
- **89% code reduction**: From 2,947-line single file to 309-line main app + 13 focused modules
- **Zero indentation errors**: Eliminated editing issues with small, focused files
- **Professional Blueprint architecture**: Clean separation of concerns for enterprise-grade maintainability
- **✅ API COMPATIBILITY RESTORED**: All Blueprint routes now match original functionality exactly
- **🔧 MAJOR FIX (Oct 1, 2025)**: Fixed critical API contract differences between original and Blueprint implementations
- **🎯 UX REVOLUTION (Oct 2, 2025)**: Unified PDF display system - all document previews now use consistent iframe approach with automatic image-to-PDF conversion
- **🔧 CRITICAL UI FIXES (Oct 2, 2025)**: Fixed OCR rescan functionality, eliminated popup alerts, improved PDF scaling, implemented rotation persistence, added LLM reanalysis capabilities
- **⚡ SMART PROCESSING (Oct 3, 2025)**: Unified SSE progress stream (analysis + processing), token-based cancellation, dual-batch separation, normalized PDF cache, forced rotation carry-forward for OCR
 - **♻️ RESCAN STABILITY (Oct 7, 2025)**: Legacy-first AI classification ordering for deterministic tests, resilient filename regeneration (even with empty OCR text), FAST_TEST_MODE integration for LLM-only rescans

**Key Features:**
- End-to-end document workflow: Intake → OCR → AI Classification → Human Verification → Export
- **Unified Document Display**: Revolutionary PDF standardization - all images automatically converted to PDF for consistent preview experience across all templates
- **Enhanced Single Document Workflow**: Streamlined processing with AI-powered category and filename suggestions
- **Intelligent AI Filename Generation**: Content-based filename suggestions using document analysis
- **Interactive Manipulation Interface**: Edit AI suggestions with dropdown categories and filename options
- **Individual Document Rescan**: Re-analyze specific documents for improved AI results
- **Template Consistency**: All 5 preview templates use identical iframe approach - no more display inconsistencies or rotation issues
- LLM-powered document analysis with Ollama integration
- Complete file safety with rollback mechanisms
- RAG-ready data structure for future AI integration
- Modern Flask web interface with guided workflows
- **Modular Blueprint Architecture**: 6 route modules + 3 service layers for maximum maintainability
- **Smart Processing Orchestration**: Real-time Server-Sent Events (SSE) progress with cancellation support and consolidated UI feedback
- **Persistent Normalized PDF Cache**: Hash-based image→PDF conversion reuse across runs with automatic garbage collection
- **Forced Rotation Carry-Forward**: User or analysis-detected rotation instantly applied during OCR (skips multi-angle auto detection)
 - **Runtime Rotation Serving & Cache**: On-demand rotation application (90/180/270) with timestamp-based cache invalidation and double-rotation prevention.
 - **Deterministic Rescan Path**: LLM-only rescans prioritize legacy simple classifier first (monkeypatch friendly) then refine with structured classifier for confidence/summary enrichment.
 - **Adaptive Filename Generation**: Intelligent regeneration triggers on category change or content hash shift—no dependency on non-empty OCR text in test mode.

**Architecture:**
- **Modular Design**: Routes organized by functionality (intake, batch, manipulation, export, admin, api)
- **Service Layer**: Separate business logic from web interface concerns
- **Clean Imports**: Proper Python package structure with relative imports
- **Maintainable**: Small, focused files instead of massive monolithic code

**Status:** ✅ Production Ready  
**Tech Stack:** Python 3, Flask Blueprints, SQLite, Ollama LLM, EasyOCR/Tesseract

**🤖 AI Assistants:** See [`.github/copilot-instructions.md`](.github/copilot-instructions.md) for critical setup patterns and common mistake prevention.

[📖 Full Documentation](doc_processor/readme.md)

### 🛠️ Utility Tools (`tools/`)

#### **`download_manager/`**
Download management utilities with GUI interface for batch file operations.

#### **`file_utils/`**
File manipulation utilities including regex-based copy operations.

#### **`gamelist_editor/`**
XML gamelist editor for retro gaming collections and metadata management.

#### **`sdcard_imager/`**
SD card imaging utility for backup and restoration operations.

### 🗂️ Working Directories

All document processing directories are now properly organized within `doc_processor/`:

#### **Document Processing Directories** (in `doc_processor/`)
- **`intake/`** - Incoming PDFs for processing
- **`processed/`** - Work-in-progress document staging
- **`archive/`** - Processed file archives
- **`filing_cabinet/`** - Final categorized document storage
- **`logs/`** - Application and system logs
- **`instance/`** - Flask application instance data
- **`venv/`** - Python virtual environment

#### **Repository Infrastructure**
- **`.github/`** - GitHub workflows and repository configuration

### 📚 Legacy & Experimental

#### **`Document_Scanner_Gemini_outdated/`** (260KB)
Legacy document scanner implementation using Google Gemini API.  
*Status: Archived - superseded by doc_processor (source code only, venv removed)*

#### **`Document_Scanner_Ollama_outdated/`** (164KB)
Legacy document scanner using Ollama integration.  
*Status: Archived - superseded by doc_processor (source code only, venv removed)*

## Quick Start

## Documentation

For detailed subsystem and workflow documentation:

- **Docs Index:** [`doc_processor/docs/README.md`](doc_processor/docs/README.md)
- **Usage Guide:** [`doc_processor/docs/USAGE.md`](doc_processor/docs/USAGE.md)
- **Legacy / Deprecation Policy:** [`doc_processor/docs/LEGACY_CODE.md`](doc_processor/docs/LEGACY_CODE.md)
- **AI / LLM Detection Details:** [`doc_processor/docs/LLM_DETECTION.md`](doc_processor/docs/LLM_DETECTION.md)
- **Deep Processor README:** [`doc_processor/readme.md`](doc_processor/readme.md)

All new deep-dive technical docs should live under `doc_processor/docs/` and be linked from the Docs Index.

### For Document Processing:
```bash
# 1) One-time environment setup
cd doc_processor
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python dev_tools/database_setup.py
cp .env.sample .env  # Edit with your settings

# 2) Start the application (from repo root) — REQUIRED
cd ..
./start_app.sh
```

Access the web interface at `http://localhost:5000`.

Important:
- Always use `./start_app.sh`. It activates the correct venv and runs `python -m doc_processor.app` from the repo root.
- Don’t run `python app.py` or run from the `doc_processor/` subdirectory—imports will fail.
- Smart processing workflow lives under `Batch Control` → “Smart Process” (streams progress and exposes cancel button when active).
 - FAST_TEST_MODE (set in `.env`) short-circuits heavy OCR & AI calls where possible to produce deterministic, fast test outcomes; rescan endpoint honors this mode.

#### Rescan Behavior (OCR / LLM)
Endpoint: `/api/rescan_document/<id>`

Modes:
- `llm_only`: Reuses stored OCR text, runs legacy simple classifier first (enables deterministic monkeypatching in tests) then optional structured classifier for confidence + reasoning.
- `ocr_and_llm`: Re-runs OCR (honoring logical rotation), persists updated text, then performs AI classification.
- `ocr`: Only refreshes OCR fields; AI suggestions untouched.

Filename Generation Logic:
- Regenerates when (a) no previous suggestion, (b) category changed but filename remained the same, or (c) OCR text content hash changed.
- In FAST_TEST_MODE, regeneration still occurs even with empty/mocked text—supporting unit test determinism.
- Legacy-first ordering ensures monkeypatched `get_ai_classification` influences category and filename before structured classifier refinement.

Throttling:
- AI classification skipped if prior LLM rescan < 5 seconds ago (throttled flag returned).

Return Payload Highlights:
```
{
   "ai_category": "Invoice",
   "ai_filename": "2025_Invoice_Test",
   "updated": {"ocr": false, "ai": true},
   "throttled_ai": false
}
```

Planned Enhancements:
- Confidence reconciliation strategy when legacy and structured classifiers disagree.
- Optional override to force filename regeneration even if neither category nor hash changed.

### For Utility Tools:
```bash
cd tools/<specific_tool>
# Follow individual tool documentation
```

## Development Setup

1. **Clone Repository:**
   ```bash
   git clone https://github.com/TaintedHorizon/Python_Testing_Vibe.git
   cd Python_Testing_Vibe
   ```

2. **Choose Your Project:**
   - **Document Processing**: See `doc_processor/readme.md`
   - **Utilities**: Browse `tools/` directory
   - **Development**: Use existing `.venv/` or create project-specific environments

3. **Environment Management:**
   ```bash
   # Use existing environment
   source .venv/bin/activate
   
   # Or create project-specific environment
   cd <project_directory>
   python -m venv venv
   source venv/bin/activate
   ```

## Project Status

| Component | Status | Description |
|-----------|--------|-------------|
| **doc_processor** | ✅ Production | Full-featured document processing system |
| **tools/download_manager** | ✅ Stable | Download management with GUI |
| **tools/file_utils** | ✅ Stable | File manipulation utilities |
| **tools/gamelist_editor** | ✅ Stable | XML gamelist management |
| **tools/sdcard_imager** | ✅ Stable | SD card imaging utility |
| **Document_Scanner_*_outdated** | 🗄️ Archived | Legacy implementations |

## Contributing

Contributions are welcome! Each project maintains its own contributing guidelines:

- **doc_processor**: See `doc_processor/CONTRIBUTING.md`
- **General**: Follow standard Python conventions and add tests where applicable

## License

This repository is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Credits

- **@TaintedHorizon** - Primary maintainer and developer
- Individual tools may have additional contributors documented in their respective directories

---

*This repository serves as both a development playground and a collection of production-ready utilities. The main focus is the document processing system in `doc_processor/`, with various supporting tools in `tools/`.*

---

## Rotation Handling & Testing

The system implements a two-tier rotation model:

1. Pre-OCR Normalization: Any persisted rotation override in `intake_rotations` is applied before OCR/searchable PDF generation so downstream AI & text extraction operate on correctly oriented pages.
2. Dynamic Serving Layer: The manipulation preview route (`/document/serve_single_pdf/<id>`) applies rotation on-the-fly (PyMuPDF) and caches the transformed PDF in `/tmp` keyed by `(doc_id, rotation)` with regeneration triggered when `updated_at` changes.

Safety & Performance Characteristics:
- Timestamp-Based Invalidation: Cached rotated PDFs are regenerated only when the corresponding rotation row’s `updated_at` advances.
- Double-Rotation Prevention: If the stored PDF’s first page already has a matching physical rotation, dynamic rotation is skipped (prevents 90° → 180° compounding artifacts).
- Directory Whitelisting: Served paths validated against allowed roots (intake/processed/normalized/archive) to mitigate path traversal.

Test Coverage (New):
- `test_rotation_serving.py`: Validates cache regeneration when rotation angle changes.
- `test_grouped_rotation.py::test_grouped_document_rotation_serving`: Asserts grouped-document parity expectations using single-document route until a native grouped route is added.
- `test_grouped_rotation.py::test_no_double_rotation`: Ensures no byte changes when a physically rotated PDF matches declared rotation (cache reuse, no duplicate transform).
- `tests/conftest.py`: Provides reusable fixtures (`temp_db_path`, `app`, `client`, `seed_conn`) standardizing isolated ephemeral DB + app factory lifecycle.

Planned Enhancements:
- Dedicated grouped-document serving endpoint assembling multi-page PDFs with rotation normalization.
- Lightweight assertion test for pre-OCR normalization side-effects (e.g., verifying searchable text alignment vs rotation).

---

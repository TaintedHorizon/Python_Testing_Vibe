
# Human-in-the-Loop Document Processing System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Project Status

**Current Status:** Production Ready - All core modules (Batch Processing, Verification, Review, Grouping, Ordering, Export) have been tested and are complete. The system includes comprehensive file safety, LLM integration, and audit trail capabilities.

## Recent Changes (September 2025)

- **Export Naming Standardization & Filing Cabinet Cleanup (September 30):**
    - **Naming Consistency**: Standardized directory and filename sanitization across single document and batch export workflows - both now use underscores instead of spaces in directory names for better filesystem compatibility
    - **Centralized Sanitization**: Unified filename sanitization using `security.sanitize_filename()` with consistent rules (non-alphanumeric → underscores, except dots/hyphens)
    - **User Input Sanitization**: Added sanitization to all user input routes (`/api/set_name`, finalize form) ensuring consistency from input to output
    - **Filing Cabinet Cleanup Tool**: New comprehensive utility (`dev_tools/cleanup_filing_cabinet_names.py`) to standardize existing directory and file names in the filing cabinet
        - Preview mode (dry-run) to see changes before applying
        - Automatic backup creation with rollback capability  
        - Smart conflict resolution with directory merging and timestamp suffixes
        - Comprehensive logging and operation tracking
        - Successfully processed 11 operations: 8 directory renames and 3 file renames with intelligent content merging

- **Document Detection Enhancement & Rotation Support & Cleanup Automation (September 29 - Update 2):**
    - **Multi-Point Document Sampling**: Enhanced document detection to sample first, middle, and last pages for accurate batch scan identification, preventing misclassification of multi-document files
    - **Automatic Rotation Detection**: Implemented OCR confidence-based rotation detection that tests all orientations and automatically applies optimal rotation during single document processing
    - **Manual Rotation Controls**: Added comprehensive rotation interface to single document workflow with visual controls (Rotate Left/Right, Reset, Apply) borrowed from batch workflow
    - **Document Boundary Detection**: Enhanced LLM analysis to detect multiple documents scanned together by identifying format inconsistencies, company changes, and topic transitions
    - **Batch Directory Cleanup**: Automated cleanup of empty batch directories after export completion with safety checks and manual cleanup tools
    - **Processing Pipeline Integration**: Rotation detection integrated into `create_searchable_pdf()` function with detailed logging of decisions and confidence scores

- **Export Button UI Fixes & Workflow Consistency (September 29):**
    - Implemented comprehensive flash message system with success/error feedback for all operations
    - Fixed export button functionality that appeared unresponsive due to JavaScript conflicts
    - Added visual feedback ("Processing..." states) for export operations in Simple Browser environment
    - Extended batch management consistency - exported single document batches now show same options as traditional batches
    - Fixed invisible "Edit Again" buttons by adding missing CSS styling classes
    - Resolved button spacing issues and ensured all action buttons are properly visible

- **Single Document Workflow Enhancement:**
    - Implemented AI-powered filename generation based on document content analysis
    - Enhanced manipulation interface with category dropdowns and three filename options
    - Added individual document rescan functionality for improved AI results
    - Fixed manipulation workflow to properly track editing status and show appropriate buttons
    - Created content-based filename suggestions using document OCR text and AI analysis
    - Streamlined save process with clear "Manipulate → Save → Export" workflow progression

- **Major project hygiene and structure improvements:**
    - All dev/admin scripts moved to `dev_tools/`
    - Added `tests/` for pytest-based testing
    - Added `docs/` for documentation and usage guides
    - Added project hygiene files: `Makefile`, `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`, `.env.sample`
    - Removed obsolete and duplicate files; validated all core `.py` files as referenced
    - Added `.gitignore` to exclude model weights and backup files from version control
    - Updated and clarified documentation throughout the project

- **LLM Integration & File Safety Improvements:**
    - Restored complete LLM functionality with OCR fallback for scanned documents
    - Implemented comprehensive file safety with `safe_move()` and rollback mechanisms
    - Fixed single document processing to use category folders (not archive)
    - Added extensive logging with emoji identifiers for easy troubleshooting
    - Enhanced configuration management with quote-stripping and fallback paths
    - Fixed duplicate database path issues with absolute path configuration

---

## Overview


This project is a web-based, human-in-the-loop document processing pipeline designed to ingest, classify, and organize scanned documents. It uses a combination of automated OCR and AI classification with a robust user interface for verification and correction, ensuring high-quality, structured data as the final output.

**Recent Updates (September 2025):**
- All configuration is now managed via `config_manager.py` and the `.env` file.
- Custom categories are now global: when you add a new category during verification or review, it is saved in the database and will appear in the dropdown for all future batches.
- The dropdowns for category selection in verify, review, and revisit always show all categories (default and custom) from the database.
- The workflow for adding custom categories is fully database-driven and persistent.

The core philosophy is to use automation for the heavy lifting (like text extraction and initial categorization) and empower a human user to quickly and efficiently verify, correct, and organize the results.

This project has recently completed Module 5, which finalizes the document processing workflow with robust export and finalization features.

## Key Features

*   **End-to-end Document Pipeline**: Intake → OCR → AI Classification → Human Verification → Grouping → Ordering → Export
*   **Enhanced Single Document Workflow**: Streamlined processing with AI-powered category and filename suggestions, manipulation interface, and individual document rescan capabilities
*   **Intelligent Document Detection**: Multi-point sampling analyzes first, middle, and last pages to accurately distinguish single documents from batch scans
*   **Automatic Rotation Detection**: OCR confidence-based rotation testing automatically corrects sideways documents during processing
*   **Manual Rotation Controls**: Visual rotation interface in single document workflow with real-time feedback and apply functionality
*   **AI-Powered Filename Generation**: Intelligent content-based filename suggestions using document analysis and OCR text
*   **Interactive Manipulation Interface**: Edit AI suggestions with category dropdowns (matching verify workflow) and three filename options: Original, AI-Generated, and Custom
*   **Individual Document Rescan**: Re-analyze specific documents for improved AI results with loading states and error handling
*   **Automated Cleanup**: Empty batch directories automatically removed after export completion with safety checks and manual cleanup tools
*   **Full Audit Trail**: Every AI prompt/response, human correction, rotation update, category change, and status transition is logged with complete traceability
*   **RAG-Ready Architecture**: All OCR text, AI outputs, human decisions, and taxonomy evolution are stored for future retrieval-augmented workflows
*   **AI-Powered Classification**: Uses a local Large Language Model (via Ollama) with intelligent fallback to OCR for scanned documents
*   **File Safety & Integrity**: Comprehensive `safe_move()` operations with verification and automatic rollback on failures
*   **Category Governance**: Add, rename (with historical trace), soft delete/restore, annotate categories with full database persistence
*   **Modern Flask Web UI**: Guided workflow with batch control, verification, review, grouping, ordering, finalization, and audit views
*   **Rotation-Safe OCR**: Re-run OCR with in-memory rotation (non-destructive) while persisting logical rotation angles
*   **Smart Document Detection**: Automatically distinguishes single documents from batch scans using LLM analysis with enhanced boundary detection
*   **Export Formats**: Each document exported as non-searchable PDF, searchable PDF (OCR layer), and structured Markdown logs
*   **Structured Logging**: JSON-based logging with emoji identifiers for easy troubleshooting and system monitoring

## Technology Stack

*   **Backend**: Python 3, Flask
*   **Database**: SQLite
*   **OCR & Pre-processing**: EasyOCR, Tesseract OCR, pdf2image
*   **AI/LLM**: A local Ollama server (e.g., running Llama 3)
*   **Frontend**: Vanilla JavaScript, HTML, CSS (with SortableJS for drag-and-drop)

doc_processor/

## Project Structure (as of September 2025)

```
doc_processor/
│
├── .env                # Local configuration file (user-created, see .env.sample)
├── .env.sample         # Example environment file for onboarding
├── app.py              # Main Flask application (web routes, UI logic)
├── config_manager.py   # Centralized configuration management (loads from .env)
├── database.py         # Data access layer (all DB queries/commands)
├── processing.py       # Core backend logic: PDF conversion, OCR, AI, file ops
├── requirements.txt    # Python dependencies
├── Makefile            # Common dev tasks (setup, test, lint, clean, run)
├── LICENSE             # MIT License
├── CONTRIBUTING.md     # Contribution guidelines
├── CHANGELOG.md        # Project changelog
├── docs/               # Documentation and usage guides
│   └── USAGE.md
├── tests/              # Pytest-based tests
│   └── test_app.py
├── dev_tools/          # All admin/dev scripts (database setup, reset, diagnostics)
│   ├── database_setup.py
│   ├── database_upgrade.py
│   ├── reset_environment.py
│   ├── restore_categories.py
│   ├── clear_grouping_ordering_only.py
│   ├── diagnose_grouping_block.py
│   ├── force_reset_batch.py
│   └── inspect_batch1_state.py
├── templates/          # HTML templates for Flask UI
│   ├── base.html
│   ├── group.html
│   ├── batch_control.html
│   ├── order_batch.html
│   ├── order_document.html
│   ├── review.html
│   ├── revisit.html
│   └── verify.html
└── documents.db        # SQLite database (ignored by git)
```

Other top-level folders:
- `tools/` — Utility scripts and GUIs (e.g., download manager, file copy, SD card imager)
- `Document_Scanner_Ollama_outdated/`, `Document_Scanner_Gemini_outdated/` — Legacy/experimental code (not core)

---
## Project Hygiene Files

- **Makefile**: Common developer tasks (setup, test, lint, clean, run)
- **LICENSE**: MIT License for open source use
- **CONTRIBUTING.md**: Guidelines for contributing, code style, and issue reporting
- **CHANGELOG.md**: Chronological record of all notable changes
- **.env.sample**: Example environment file for onboarding
- **docs/USAGE.md**: Usage guide and troubleshooting

---
## Testing

This project uses `pytest` for automated testing. All tests are located in the `tests/` directory.

To run tests:

```bash
venv/bin/pytest tests/
```

---
## .gitignore and Large Files

The following files are excluded from version control:
- Model/data weights: `Document_Scanner_Ollama_outdated/model_cache/*.pth`
- Database files: `**/documents.db`
- Python cache: `**/__pycache__/`
- Virtual environments: `venv/`
- Logs: `*.log`
- Backup files: `custom_categories_backup.json`

If you need to version large files (e.g., model weights), consider using [Git LFS](https://git-lfs.github.com/).

---
## Contributing

See `CONTRIBUTING.md` for guidelines on contributing, code style, and issue reporting.

---
## License

This project is licensed under the MIT License. See `LICENSE` for details.

---
## Troubleshooting & FAQ

- If you see `Import "pytest" could not be resolved`, install pytest in your environment: `pip install pytest`
- If you encounter issues with large files, check your `.gitignore` and consider Git LFS
- For database or environment issues, use scripts in `dev_tools/` for diagnostics and resets

---

## File-by-File Analysis

### `app.py`
The main Flask web application. Handles all routes, UI orchestration, and workflow logic. Delegates heavy processing to `processing.py` and all database operations to `database.py`. Renders HTML templates and manages user session state.

### `config_manager.py`
Centralizes all configuration loading and validation. Loads settings from `.env` and provides a type-safe `AppConfig` object for use throughout the app. All configuration is now managed here.

### `database.py`
The Data Access Layer (DAL). Contains all functions for interacting with the SQLite database, including queries (SELECT) and commands (INSERT, UPDATE, DELETE). Handles category management and batch/page/document status tracking. All categories (default and custom) are stored in the `categories` table.

### `processing.py`
The core processing engine. Handles PDF-to-image conversion, OCR (EasyOCR/Tesseract), AI classification (Ollama), file management, and export logic. Called by `app.py` for all intensive backend tasks.

### `templates/`
All Jinja2 HTML templates for the Flask UI. Key templates:
- `base.html`: Main base template, includes navigation and layout
- `mission_control.html`: Dashboard and workflow hub
- `verify.html`: Page-by-page verification UI
- `review.html`: Flagged page review and correction
- `group.html`: Grouping pages into documents
- `order_batch.html`, `order_document.html`: Page ordering UIs
- `finalize.html`: Final review and export
- `revisit.html`, `view_batch.html`, `view_documents.html`: Read-only and batch/document views

### `dev_tools/`
All admin/dev scripts for setup, maintenance, and diagnostics:
- `database_setup.py`: Initialize a new database (idempotent)
- `database_upgrade.py`: Safely upgrade DB schema (add columns, etc.)
- `reset_environment.py`: Wipe all data and reset environment for testing
- `restore_categories.py`: Restore custom categories from backup
- `clear_grouping_ordering_only.py`: Clear grouping/ordering for a batch
- `diagnose_grouping_block.py`: Diagnose grouping issues in the DB
- `force_reset_batch.py`: Force reset a batch to initial state
- `inspect_batch1_state.py`: Inspect all DB state for batch 1
- `cleanup_filing_cabinet_names.py`: Standardize directory and file names in filing cabinet (preview, backup, rollback)
- `cleanup_empty_batch_directories.py`: Remove empty batch directories from work-in-progress folder

### `tests/`
All automated tests (pytest). Add new tests here to cover routes, processing, and database logic. Example: `test_app.py` checks the home route and UI text.

### `docs/`
Documentation and usage guides. Example: `USAGE.md` covers quick start, workflow, and troubleshooting.

### Project Hygiene Files
- `Makefile`: Common dev tasks (setup, test, lint, clean, run)
- `LICENSE`: MIT License
- `CONTRIBUTING.md`: Contribution guidelines
- `CHANGELOG.md`: Chronological record of changes
- `.env.sample`: Example environment file for onboarding

### Other Folders
- `tools/`: Utility scripts and GUIs (download manager, file copy, SD card imager, etc.)
- `Document_Scanner_Ollama_outdated/`, `Document_Scanner_Gemini_outdated/`: Legacy/experimental code (not core)

---

## Audit & RAG Integration

This system is designed with full auditability and future RAG (Retrieval-Augmented Generation) integration in mind:

- **Complete Document Trail**: All document/page-level OCR text is stored in the database for retrieval
- **Interaction Logging**: The `interaction_log` table records every AI and human action, correction, and status change with batch/document/user/timestamp context
- **Category Evolution**: The `category_change_log` provides immutable lineage for taxonomy changes (rename, add, restore, delete)
- **AI Decision Context**: All AI prompts, responses, and confidence scores are preserved for future analysis
- **Human Feedback Loop**: Every human correction and decision is captured, enabling future LLMs to learn from human expertise
- **Export Metadata**: Each exported document includes comprehensive Markdown logs with processing history and human decisions

This rich data foundation enables future LLMs to use Retrieval-Augmented Generation with full process history, human feedback patterns, and document classification expertise.

---

## Setup and Installation (Ubuntu)

**1. Install System Dependencies:**

These libraries are required for Tesseract OCR and PDF-to-image conversion.

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr poppler-utils sqlite3 -y
```

**2. Set up Python Environment & Install Packages:**

It is highly recommended to use a virtual environment to manage project dependencies.

```bash
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install all required Python packages
pip install -r requirements.txt
```


**3. Configure Environment Variables:**

Copy `.env.sample` to `.env` and edit as needed. All configuration is now loaded from this file via `config_manager.py`. For detailed configuration options, see `docs/USAGE.md`.

```bash
cp .env.sample .env
# Edit .env to set your paths and options
```

Alternatively, you can create a `.env` file manually with the following template:

```
# --- Directory Paths (use absolute paths) ---
INTAKE_DIR=/path/to/your/intake_folder
PROCESSED_DIR=/path/to/your/processed_folder
ARCHIVE_DIR=/path/to/your/archive_folder
DATABASE_PATH=/path/to/your/database/documents.db
FILING_CABINET_DIR=/path/to/your/filing_cabinet

# --- Ollama LLM Configuration ---
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_CONTEXT_WINDOW=8192

# --- Task-Specific Context Windows ---
# These control AI context window sizes for different tasks
# Smaller contexts = faster inference, larger contexts = better quality
OLLAMA_CTX_CLASSIFICATION=2048    # Document category classification
OLLAMA_CTX_DETECTION=2048         # Single vs batch document detection
OLLAMA_CTX_CATEGORY=2048          # Page category assignment
OLLAMA_CTX_ORDERING=2048          # Page ordering within documents
OLLAMA_CTX_TITLE_GENERATION=4096  # Document title generation (needs more context)

# --- Debugging ---
# Set to "true" to skip the slow OCR process for faster UI testing.
DEBUG_SKIP_OCR=false
```

### 🎛️ **AI Context Window Tuning**

The system uses different context window sizes for different AI tasks to optimize performance and quality. The system automatically logs context usage for each task:

```bash
[LLM DETECTION] Context: 750~tokens/2048 (36.6% usage)
[LLM TITLE_GENERATION] Context: 1800~tokens/4096 (43.9% usage)
```

**Tuning Guidelines:**
- **High usage (>80%)**: Consider increasing the context window
- **Low usage (<30%)**: Consider decreasing for better performance
- **Context overflow**: Increase immediately to prevent quality degradation

**Common Adjustments:**
- Increase `OLLAMA_CTX_TITLE_GENERATION` to 6144+ for complex documents
- Decrease `OLLAMA_CTX_CLASSIFICATION` to 1024 for simple categorization
- Monitor logs and adjust based on actual usage patterns

**4. Initialize the Database:**

This command creates the SQLite database file and sets up all the necessary tables.

```bash
python dev_tools/database_setup.py
```

**5. (If Upgrading) Run the Upgrade Script:**

If you have an existing database and have pulled new code that changes the schema, run this script to safely add new columns without losing your data.

```bash
python dev_tools/database_upgrade.py
```

## How to Run & Use

**1. Start the Server:**

```bash
python -m doc_processor.app
```

**2. Access the Application:**

Open your web browser and go to `http://<your_vm_ip>:5000`. This will take you to the "Batch Control" page.

**3. Workflow Guide:**

For detailed usage instructions and troubleshooting, see `docs/USAGE.md`. The basic workflow is:

1.  **Place Files**: Add new PDF documents into the folder you specified as your `INTAKE_DIR`.
2.  **Start Batch**: On the Batch Control page, click the "Start New Batch" button. The system will process all files from the intake folder.
3.  **Verify**: A new batch will appear. Click the "Verify" button. Go through each page, approving the AI's category or selecting a new one. You can add a new custom category at any time; it will be saved globally and appear in all future dropdowns. Use the "Flag for Review" button if a page has issues (e.g., poor OCR, upside down).
4.  **Review (If Needed)**: If you flagged any pages, a "Review" button will appear. Use this page to fix rotations, re-run OCR, or delete bad pages. All categories (default and custom) are always available in the dropdown.
5.  **Group**: Once verification is complete, click the "Group" button. On this screen, select pages from the same category and give them a document name (e.g., "January 2024 Bank Statement").
6.  **Order**: After grouping, click the "Order Pages" button. This will show you all documents with more than one page. Click "Order Pages" on a document to go to the drag-and-drop interface to set the correct page sequence.
7.  **Finalize & Export**: Once all documents are ordered, click the "Finalize & Export" button. On this screen, you can review and edit the AI-suggested filenames before clicking "Export All Documents". The final files will be saved to your `FILING_CABINET_DIR`.
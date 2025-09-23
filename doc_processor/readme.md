
# Human-in-the-Loop (HITL) Document Processing System

## Recent Changes (September 2025)

- **Major project hygiene and structure improvements:**
    - All dev/admin scripts moved to `dev_tools/`
    - Added `tests/` for pytest-based testing
    - Added `docs/` for documentation and usage guides
    - Added project hygiene files: `Makefile`, `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`, `.env.sample`
    - Removed obsolete and duplicate files; validated all core `.py` files as referenced
    - Added `.gitignore` to exclude model weights and backup files from version control
    - Updated and clarified documentation throughout the project

---

## Overview


This project is a web-based, human-in-the-loop document processing pipeline designed to ingest, classify, and organize scanned documents. It uses a combination of automated OCR and AI classification with a robust user interface for verification and correction, ensuring high-quality, structured data as the final output.

**Recent Updates (September 2025):**
- All configuration is now managed via `config_manager.py` and the `.env` file. The old `config.py` is no longer used.
- Custom categories are now global: when you add a new category during verification or review, it is saved in the database and will appear in the dropdown for all future batches.
- The dropdowns for category selection in verify, review, and revisit always show all categories (default and custom) from the database.
- The workflow for adding custom categories is fully database-driven and persistent.

The core philosophy is to use automation for the heavy lifting (like text extraction and initial categorization) and empower a human user to quickly and efficiently verify, correct, and organize the results.

This project has recently completed Module 5, which finalizes the document processing workflow with robust export and finalization features.

## Features

*   **Automated Ingestion**: Automatically processes all PDFs from a designated intake folder.
*   **OCR and Pre-processing**: Converts PDFs to images, detects and corrects page orientation, and extracts text using EasyOCR and Tesseract.
*   **AI-Powered Classification**: Uses a local Large Language Model (via Ollama) to provide an initial "best guess" category for each page.
*   **Guided Web Interface**: A step-by-step workflow presented in a central "Mission Control" dashboard that guides the user through each stage.
*   **Verification & Correction**: A rapid, page-by-page UI to approve or correct AI-suggested categories.
*   **Flagging & Review**: A safety net to flag problematic pages for a dedicated review process, where OCR can be re-run with manual rotation.
*   **Interactive Document Grouping**: A user-friendly interface to assemble individual verified pages into logical, multi-page documents.
*   **Drag-and-Drop Page Ordering**: An intuitive, two-column UI with a large preview pane and a drag-and-drop list for reordering pages within a document.
*   **Robust AI-Assisted Ordering**: A hybrid AI feature that reliably suggests page order by extracting printed page numbers, which are then used for a code-based sort.
*   **Finalization and Export**: A final review stage to edit AI-suggested filenames and export documents into a clean, categorized folder structure as standard PDFs, searchable PDFs, and detailed Markdown log files.

## Technology Stack

*   **Backend**: Python 3, Flask
*   **Database**: SQLite
*   **OCR & Pre-processing**: EasyOCR, Tesseract, pdf2image
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
│   ├── mission_control.html
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

This is the heart of the web application. It uses the Flask framework to define all the URL routes and handle the logic for the user interface. It orchestrates the entire user workflow, from initiating a new batch to verifying pages, grouping them into documents, ordering them, and finally exporting them. It doesn't perform the heavy lifting itself but instead calls functions from `processing.py` for tasks like OCR and `database.py` to read or write data. It is responsible for rendering the HTML templates and passing the necessary data to them.


### `config_manager.py`
Centralizes all configuration loading and validation. Loads settings from `.env` and provides a type-safe `AppConfig` object for use throughout the app. All configuration is now managed here.

### `database.py`
This module is the Data Access Layer (DAL). It contains all the functions that interact directly with the SQLite database. By centralizing all SQL queries here, the rest of the application can be database-agnostic, and the code is much cleaner and easier to maintain. The functions are divided into "queries" (reading data with `SELECT`) and "commands" (modifying data with `INSERT`, `UPDATE`, `DELETE`). It also includes helpers for category management:
- All categories (default and custom) are stored in the `categories` table.
- When a user adds a new custom category, it is inserted into the global table if not already present (case-insensitive).

### `database_setup.py`

This is a one-time setup script used to initialize a new, empty database with the correct schema. It creates all the necessary tables (`batches`, `pages`, `documents`, `document_pages`) and defines their columns, primary keys, and foreign key relationships. It is idempotent, meaning it can be run multiple times without causing errors.

### `database_upgrade.py`

This script is for managing database schema changes over time. As new features are added, you might need to add a new column to a table. This script provides a safe, non-destructive way to do that. It checks if a column already exists before adding it, ensuring that it can be run multiple times without causing issues and without destroying existing data. This is a crucial script for maintaining a production application.

### `processing.py`

This is the "engine" of the application. It contains all the core data processing logic. This includes converting PDFs to images, running OCR to extract text, communicating with the Ollama AI to get suggestions for categories and filenames, generating the final PDF and Markdown files, and managing the file system (creating directories, moving files, and cleaning up). This module is called by `app.py` to perform these intensive tasks in the background.

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

Create a file named `.env` in the `doc_processor` directory. This file stores your local configuration. All configuration is now loaded from this file via `config_manager.py`. Copy and paste the following, adjusting the paths to match your system.

```
# --- Directory Paths (use absolute paths) ---
INTAKE_DIR=/path/to/your/intake_folder
PROCESSED_DIR=/path/to/your/processed_folder
ARCHIVE_DIR=/path/to/your/archive_folder
DATABASE_PATH=/path/to/your/database/documents.db
FILING_CABINET_DIR=/path/to/your/filing_cabinet

# --- Ollama AI Configuration ---
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3

# --- Debugging ---
# Set to "true" to skip the slow OCR process for faster UI testing.
DEBUG_SKIP_OCR=false
```

**4. Initialize the Database:**

This command creates the SQLite database file and sets up all the necessary tables.

```bash
python doc_processor/database_setup.py
```

**5. (If Upgrading) Run the Upgrade Script:**

If you have an existing database and have pulled new code that changes the schema, run this script to safely add new columns without losing your data.

```bash
python doc_processor/upgrade_database.py
```

## How to Run & Use

**1. Start the Server:**

```bash
python doc_processor/app.py
```

**2. Access the Application:**

Open your web browser and go to `http://<your_vm_ip>:5000`. This will take you to the "Mission Control" page.

**3. Workflow Guide:**

1.  **Place Files**: Add new PDF documents into the folder you specified as your `INTAKE_DIR`.
2.  **Start Batch**: On the Mission Control page, click the "Start New Batch" button. The system will process all files from the intake folder.
3.  **Verify**: A new batch will appear. Click the "Verify" button. Go through each page, approving the AI's category or selecting a new one. You can add a new custom category at any time; it will be saved globally and appear in all future dropdowns. Use the "Flag for Review" button if a page has issues (e.g., poor OCR, upside down).
4.  **Review (If Needed)**: If you flagged any pages, a "Review" button will appear. Use this page to fix rotations, re-run OCR, or delete bad pages. All categories (default and custom) are always available in the dropdown.
5.  **Group**: Once verification is complete, click the "Group" button. On this screen, select pages from the same category and give them a document name (e.g., "January 2024 Bank Statement").
6.  **Order**: After grouping, click the "Order Pages" button. This will show you all documents with more than one page. Click "Order Pages" on a document to go to the drag-and-drop interface to set the correct page sequence.
7.  **Finalize & Export**: Once all documents are ordered, click the "Finalize & Export" button. On this screen, you can review and edit the AI-suggested filenames before clicking "Export All Documents". The final files will be saved to your `FILING_CABINET_DIR`.
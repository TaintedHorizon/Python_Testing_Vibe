# Human-in-the-Loop (HITL) Document Processing System

## Overview

This project is a web-based, human-in-the-loop document processing pipeline designed to ingest, classify, and organize scanned documents. It uses a combination of automated OCR and AI classification with a robust user interface for verification and correction, ensuring high-quality, structured data as the final output.

The core philosophy is to use automation for the heavy lifting (like text extraction and initial categorization) and empower a human user to quickly and efficiently verify, correct, and organize the results.

## Technology Stack

*   **Backend**: Python 3, Flask
*   **Database**: SQLite
*   **OCR & Pre-processing**: EasyOCR, Tesseract, pdf2image, PyMuPDF
*   **AI/LLM**: A local Ollama server (e.g., running Llama 3) communicated with via `requests`.
*   **Frontend**: Vanilla JavaScript, HTML, CSS
*   **Dependencies**: `requirements.txt` tracks all Python packages, including Pillow, SQLAlchemy, and python-dotenv.

## Project Structure and File Analysis

This project is organized into several key files and directories, each with a specific role.

```
doc_processor/
│
├── .env                    # LOCAL ONLY: Stores secret keys and environment-specific paths.
├── .gitignore              # Specifies files and directories for Git to ignore.
├── app.py                  # Main Flask application: handles web routes and user workflow.
├── custom_categories_backup.json # Automatically generated backup of user-added categories.
├── database.py             # Data Access Layer: all functions that query the database.
├── database_setup.py       # Utility script to initialize a new database from scratch.
├── database_upgrade.py     # Utility script to safely add new columns to an existing database.
├── documents.db            # The SQLite database file (ignored by Git).
├── processing.py           # The application's engine: handles OCR, AI calls, and file generation.
├── readme.md               # This documentation file.
├── requirements.txt        # Lists all required Python packages for easy installation.
├── reset_environment.py    # DESTRUCTIVE utility to wipe the database and processed files for a clean start.
├── restore_categories.py   # Utility to restore custom categories into a clean database after a reset.
│
└── templates/              # Contains all HTML templates for the web interface.
    ├── base.html           # The master template providing consistent layout and navigation.
    ├── finalize.html       # Step 5: UI to edit final filenames and export the batch.
    ├── group.html          # Step 3: UI to group verified pages into logical documents.
    ├── index.html          # A simple, alternative starting page to kick off a batch.
    ├── mission_control.html# The main dashboard and central hub for the user workflow.
    ├── order_batch.html    # Step 4a: A page to select which document's pages to order.
    ├── order_document.html # Step 4b: UI with drag-and-drop to reorder pages within a document.
    ├── review.html         # Step 2a: UI to fix rotation and re-run OCR on flagged pages.
    ├── revisit.html        # A read-only view to inspect pages of an already-processed batch.
    ├── verify.html         # Step 2: The main UI for page-by-page category verification.
    ├── view_batch.html     # A read-only view to inspect the documents in a completed batch.
    └── view_documents.html # A read-only view to inspect the pages of a document in a completed batch.
```

---

### Core Application Files

These three files form the backbone of the application's functionality.

*   **`app.py` (The Conductor)**: This is the heart of the web application. It uses the Flask framework to define all the URL routes and handle the logic for the user interface. It orchestrates the entire user workflow, from initiating a new batch to verifying pages, grouping them, ordering them, and finally exporting them. It doesn't perform the heavy lifting itself but instead calls functions from `processing.py` for intensive tasks and `database.py` to read or write data.

*   **`processing.py` (The Engine)**: This module contains all the core data processing logic. This includes converting PDFs to images, running OCR to extract text, communicating with the Ollama AI to get suggestions for categories and filenames, generating the final PDF and Markdown files, and managing the file system (creating directories, moving files). This module is called by `app.py` to perform these tasks.

*   **`database.py` (The Librarian)**: This module is the Data Access Layer (DAL). It centralizes all functions that interact directly with the SQLite database. By isolating all SQL queries here, the rest of the application remains clean and easier to maintain. Functions are divided into "queries" (reading data with `SELECT`) and "commands" (modifying data with `INSERT`, `UPDATE`, `DELETE`).

---

### User Interface (`templates/`)

The `templates` directory contains all the HTML files that the user sees in their browser. They use the Jinja2 templating engine.

*   **`base.html`**: This is the most important template. It defines the common HTML structure, including the navigation bar and overall styling, that all other pages inherit. This ensures a consistent look and feel across the entire application.

*   **`mission_control.html`**: The main dashboard. It's the first page the user sees and serves as the central hub, displaying the status of all batches and providing the entry point for each step of the workflow (Verify, Group, Order, etc.).

*   **Workflow Templates**:
    *   `verify.html`: The first major step. Provides a rapid, page-by-page UI to approve or correct AI-suggested categories.
    *   `review.html`: A special step for pages that were "flagged" during verification. It allows the user to fix page rotation and re-run the OCR process.
    *   `group.html`: A two-column interface where users assemble individual verified pages into logical, multi-page documents.
    *   `order_document.html`: An intuitive drag-and-drop interface for reordering the pages within a single document.
    *   `finalize.html`: The final step, where the user can edit the AI-suggested filenames before clicking the export button.

---

### Configuration & Developer Scripts

These files are not part of the core runtime logic but are essential for setup, development, and maintenance.

*   **`requirements.txt`**: Lists all the Python packages the project depends on. Running `pip install -r requirements.txt` is the standard way to set up the project's environment, ensuring that the correct versions of all tools are installed.

*   **`.gitignore`**: A configuration file for the Git version control system. It lists files and directories that should be ignored and never committed to the repository. This includes the Python virtual environment (`venv/`), the local configuration file (`.env`), and the database itself (`documents.db`), keeping the repository clean and secure.

*   **`database_setup.py`**: A one-time setup script used to initialize a new, empty database with the correct schema. It creates all the necessary tables and defines their relationships.

*   **`database_upgrade.py`**: A maintenance script for managing database schema changes over time. It allows you to add new columns to existing tables without destroying the data that's already there.

*   **`reset_environment.py`**: A **destructive** utility script for developers. It completely wipes the database and clears out all processed files. Before deleting the database, it automatically backs up any custom categories the user has created to `custom_categories_backup.json`. This provides a clean slate for testing. **Do not run this in a production environment.**

*   **`restore_categories.py`**: The companion to the reset script. It reads the `custom_categories_backup.json` file and repopulates the clean database with the saved custom categories. This is a major convenience for developers, as it means they don't have to manually recreate their test categories after every reset.

---

## Setup and Installation (Ubuntu)

**1. Install System Dependencies:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr poppler-utils sqlite3 -y
```

**2. Set up Python Environment & Install Packages:**
```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install all required Python packages
pip install -r requirements.txt
```

**3. Configure Environment Variables:**
Create a file named `.env` in the `doc_processor` directory. Copy the template below and adjust the paths for your system. **Use absolute paths.**
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
```bash
python doc_processor/database_setup.py
```

## How to Run & Use

**1. Start the Server:**
```bash
python doc_processor/app.py
```

**2. Access the Application:**
Open your web browser and go to `http://<your_vm_ip>:5000`. This will take you to the "Mission Control" page.

**3. Workflow Guide:**
1.  **Place Files**: Add new PDF documents into your `INTAKE_DIR`.
2.  **Start Batch**: On Mission Control, click "Start New Batch".
3.  **Verify**: A new batch will appear. Click "Verify" to approve or correct AI-suggested categories for each page.
4.  **Review (If Needed)**: If you flagged pages, a "Review" button appears. Use this to fix rotations or re-run OCR.
5.  **Group**: Once verified, click "Group" to assemble pages into named documents.
6.  **Order**: Click "Order Pages" for any multi-page documents and use the drag-and-drop interface to set the correct sequence.
7.  **Finalize & Export**: Click "Finalize & Export", edit the final filenames if needed, and click "Export All Documents". The final files will be saved to your `FILING_CABINET_DIR`.

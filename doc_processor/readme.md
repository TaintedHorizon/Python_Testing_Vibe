# Human-in-the-Loop (HITL) Document Processing System

## Overview

This project is a web-based, human-in-the-loop document processing pipeline designed to ingest, classify, and organize scanned documents. It uses a combination of automated OCR and AI classification with a robust user interface for verification and correction, ensuring high-quality, structured data as the final output.

The core philosophy is to use automation for the heavy lifting (like text extraction and initial categorization) and empower a human user to quickly and efficiently verify, correct, and organize the results.

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

## Technology Stack

*   **Backend**: Python 3, Flask
*   **Database**: SQLite
*   **OCR & Pre-processing**: EasyOCR, Tesseract, pdf2image
*   **AI/LLM**: A local Ollama server (e.g., running Llama 3)
*   **Frontend**: Vanilla JavaScript, HTML, CSS (with SortableJS for drag-and-drop)

## Project Structure

```
doc_processor/
│
├── .env                # Local configuration file (you must create this)
├── app.py              # The main Flask application, defines all web routes and UI logic.
├── database.py         # Contains all functions for interacting with the database (queries and commands).
├── database_setup.py   # Script to initialize a new, empty database with the correct schema.
├── processing.py       # Handles the core backend logic: PDF conversion, OCR, and AI communication.
├── requirements.txt    # A list of all Python dependencies for the project.
├── upgrade_database.py # Safely upgrades an existing database with new columns without losing data.
│
└── templates/          # Directory for all HTML templates.
    ├── base.html           # The main base template that all other pages inherit from.
    ├── group.html          # Page for grouping verified pages into documents.
    ├── mission_control.html# The main dashboard and workflow hub.
    ├── order_batch.html    # Page that lists documents that need page ordering.
    ├── order_document.html # Page for re-ordering the pages within a single document.
    ├── review.html         # Page for reviewing and correcting pages that were flagged.
    ├── revisit.html        # A read-only view to look at pages of an already-processed batch.
    └── verify.html         # The first step in the workflow: page-by-page verification.
```

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

Create a file named `.env` in the `doc_processor` directory. This file stores your local configuration. Copy and paste the following, adjusting the paths to match your system.

```
# --- Directory Paths (use absolute paths) ---
INTAKE_DIR=/path/to/your/intake_folder
PROCESSED_DIR=/path/to/your/processed_folder
ARCHIVE_DIR=/path/to/your/archive_folder
DATABASE_PATH=/path/to/your/database/documents.db

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
3.  **Verify**: A new batch will appear. Click the "Verify" button. Go through each page, approving the AI's category or selecting a new one. Use the "Flag for Review" button if a page has issues (e.g., poor OCR, upside down).
4.  **Review (If Needed)**: If you flagged any pages, a "Review" button will appear. Use this page to fix rotations, re-run OCR, or delete bad pages.
5.  **Group**: Once verification is complete, click the "Group" button. On this screen, select pages from the same category and give them a document name (e.g., "January 2024 Bank Statement").
6.  **Order**: After grouping, click the "Order Pages" button. This will show you all documents with more than one page. Click "Order Pages" on a document to go to the drag-and-drop interface to set the correct page sequence.
7.  **Finalize**: Once all documents are ordered, you can click the "Finalize Batch" button. The batch is now considered complete.

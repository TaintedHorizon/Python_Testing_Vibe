# Human-in-the-Loop (HITL) Document Processing System

## Overview

This project is a web-based, human-in-the-loop document processing pipeline designed to ingest, classify, and organize scanned documents. It uses a combination of automated OCR and AI classification with a robust user interface for verification and correction, ensuring high-quality, structured data as the final output.

---

## Features Implemented (Modules 1, 2, & 2.5)

* **Automated Ingestion:** A web UI to trigger the processing of all PDFs in a designated intake folder.
* **OCR & Pre-processing:**
    * Converts multi-page PDFs into individual page images.
    * Automatically detects and corrects page orientation.
    * Uses EasyOCR to extract text from each page.
* **AI First-Pass Classification:**
    * Calls a remote Ollama LLM to get an initial "best guess" category for each page.
    * Uses a "Cumulative Context" prompt to improve AI consistency.
* **Web-Based Verification UI:**
    * A "Verify Batch" page to review each page's image, AI suggestion, and OCR text.
    * Allows for single-click approval of correct AI suggestions.
    * Provides a dynamic dropdown menu for correcting categories.
    * Supports the creation of new, custom categories on the fly.
* **Page Safety Net & Review Queue:**
    * A "Flag for Review" system to quarantine pages with critical errors (e.g., bad OCR, mismatched image/text).
    * A dedicated "Review Queue" UI to resolve flagged pages.
    * Tools to rotate images, re-run OCR on a single page, or delete corrupted pages.
* **Self-Improving Category System:** The category dropdowns are dynamically populated from both a default list and all custom categories previously created by the user.

---

## Technology Stack

* **Backend:** Python 3
* **Web Framework:** Flask
* **Database:** SQLite
* **OCR:** EasyOCR
* **Orientation Detection:** Pytesseract
* **LLM:** Remote Ollama Server
* **PDF Handling:** `pdf2image`

---

## Project Structure

doc_processor/
│
├── .env                  # Environment variables (paths, API keys, etc.)
├── app.py                # Main Flask application (routes and web logic)
├── database.py           # Database schema and helper functions
├── processing.py         # Core OCR and AI processing pipeline
├── requirements.txt      # Python package dependencies
│
├── intake/               # (External) PDFs are placed here for processing
├── processed_files/      # (External) Processed page images are saved here
│
├── static/               # (Not used yet) CSS, JS files
└── templates/
├── base.html         # Main site layout with navigation
├── index.html        # "New Batch" homepage
├── review.html       # "Review Queue" UI
└── verify.html       # "Verify Batch" UI


---

## Setup and Installation (Ubuntu)

1.  **Clone the repository (or set up the files).**

2.  **Install System Dependencies:**
    ```bash
    sudo apt-get update
    sudo apt-get install tesseract-ocr poppler-utils sqlite3 -y
    ```

3.  **Set up Python Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

4.  **Install Python Packages:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configure Environment:**
    * Create a `.env` file in the root directory.
    * Add the following variables, adjusting paths and host details for your environment:
        ```ini
        # --- Directory Paths ---
        INTAKE_DIR="/path/to/your/intake"
        PROCESSED_DIR="/path/to/your/processed_files"
        ARCHIVE_DIR="/path/to/your/processed_files/archive"

        # --- Database Path ---
        DATABASE_PATH="documents.db"

        # --- Ollama LLM Configuration ---
        OLLAMA_HOST="http://your_ollama_ip:11434"
        OLLAMA_MODEL="llama3.1:8b"
        OLLAMA_CONTEXT_WINDOW=8192

        # --- Debugging Flags ---
        DEBUG_SKIP_OCR="False"
        ```

6.  **Initialize the Database:**
    * Run the database script once to create the `documents.db` file and tables.
        ```bash
        python database.py
        ```

---

## How to Run

1.  **Activate the virtual environment:**
    ```bash
    source venv/bin/activate
    ```
2.  **Start the web server:**
    ```bash
    python app.py
    ```
3.  **Access the application** by navigating to `http://<your_vm_ip>:5000` in a web browser.
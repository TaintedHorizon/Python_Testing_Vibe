# Human-in-the-Loop (HITL) Document Processing System

## Overview

This project is a web-based, human-in-the-loop document processing pipeline designed to ingest, classify, and organize scanned documents. It uses a combination of automated OCR and AI classification with a robust user interface for verification and correction, ensuring high-quality, structured data as the final output.

---

## Features Implemented (Modules 1, 2, 2.5, & 3)

* **Automated Ingestion & AI First-Pass:** A web UI to trigger the OCR and initial AI classification of all pages in a batch.
* **"Mission Control" Workflow Hub:** A central dashboard (`mission_control.html`) that provides a complete overview of all batches and intelligent "next action" buttons for each stage of the workflow.
* **Web-Based Verification UI:** A page for rapid, page-by-page approval or correction of AI-suggested categories, complete with a self-improving, dynamic category list.
* **Page Safety Net & Review Queue:** A robust system to flag and quarantine pages with critical errors (bad OCR, data mismatches) and a dedicated UI to resolve these issues by re-running OCR, deleting pages, or manually correcting data.
* **Document Grouping UI:** An interactive interface (`group.html`) to assemble verified pages into final, multi-page documents. Features include:
    * An interactive preview pane to view large images of each page.
    * "Select All" functionality for quickly grouping pages by category.
    * The ability to "Revisit Grouping" to reset and re-do the document assembly for a batch.

---

## Technology Stack

* **Backend:** Python 3, Flask
* **Database:** SQLite
* **OCR & Pre-processing:** EasyOCR, Pytesseract, `pdf2image`
* **LLM:** Remote Ollama Server

---

## Project Structure

doc_processor/
│
├── .env
├── app.py
├── database.py
├── processing.py
├── requirements.txt
│
└── templates/
├── base.html
├── group.html
├── mission_control.html
├── review.html
├── revisit.html
└── verify.html


---

## Setup and Installation (Ubuntu)

1.  **Install System Dependencies:**
    ```bash
    sudo apt-get update
    sudo apt-get install tesseract-ocr poppler-utils sqlite3 -y
    ```
2.  **Set up Python Environment & Install Packages:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Configure `.env` file** with your specific directory paths and Ollama host details.
4.  **Initialize the Database:**
    ```bash
    python database.py
    ```

---

## How to Run & Use

1.  **Start the server:** `python app.py`
2.  **Access the application** at `http://<your_vm_ip>:5000`. This will take you to the "Mission Control" page.
3.  **Start a New Batch:** Click the "Start New Batch" button.
4.  **Verify, Review, Group:** Use the "smart" action buttons on the Mission Control page to guide you through the verification, review, and grouping process for each batch.

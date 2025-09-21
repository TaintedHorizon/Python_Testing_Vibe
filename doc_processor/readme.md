Human-in-the-Loop (HITL) Document Processing System
Overview
This project is a web-based, human-in-the-loop document processing pipeline designed to ingest, classify, and organize scanned documents. It uses a combination of automated OCR and AI classification with a robust user interface for verification and correction, ensuring high-quality, structured data as the final output.

Features Implemented
Module 1 & 2: Ingestion, Verification, and Review

A web UI to trigger the OCR and initial AI classification of all pages in a new batch.

A "Mission Control" workflow hub that provides a complete overview of all batches and intelligent "next action" buttons for each stage.

A page for rapid, page-by-page approval or correction of AI-suggested categories.

A page safety net and dedicated "Review" queue to handle pages flagged with errors, allowing for re-running OCR, deleting pages, or correcting categories.

Module 3: Document Grouping

An interactive interface to assemble verified pages into final, multi-page documents.

Features an interactive preview pane and "Select All" functionality for quickly grouping pages by category.

Module 4: Page Ordering & Finalization

A two-column UI with a large preview pane and a drag-and-drop list for manually reordering pages within a document.

A highly robust, hybrid AI "Suggest Order" feature that uses a two-step "Extract, then Sort" method. The LLM's primary job is to extract printed page numbers from each page, which are then used for a reliable, code-based sort.

Visual state tracking to indicate which documents have already been ordered ("Revisit Order").

Logic to automatically bypass ordering for single-page documents and finalize batches where no ordering is required.

Technology Stack
Backend: Python 3, Flask

Database: SQLite

OCR & Pre-processing: EasyOCR, Pytesseract, pdf2image

LLM: Remote Ollama Server

Project Structure
doc_processor/
│
├── .env
├── app.py
├── database.py
├── database_setup.py
├── processing.py
├── requirements.txt
├── upgrade_database.py
│
└── templates/
    ├── base.html
    ├── group.html
    ├── mission_control.html
    ├── order_batch.html
    ├── order_document.html
    ├── review.html
    ├── revisit.html
    └── verify.html
Setup and Installation (Ubuntu)
Install System Dependencies:

Bash

sudo apt-get update
sudo apt-get install tesseract-ocr poppler-utils sqlite3 -y
Set up Python Environment & Install Packages:

Bash

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
Configure .env file with your specific directory paths and Ollama host details.

Initialize the Database:

Bash

python doc_processor/database_setup.py
(If Upgrading an Existing Database) Run the Upgrade Script:

Bash

python doc_processor/upgrade_database.py
How to Run & Use
Start the server: python doc_processor/app.py

Access the application at http://<your_vm_ip>:5000. This will take you to the "Mission Control" page.

Use the "smart" action buttons on the Mission Control page to guide you through the workflow: Verify -> Group -> Order -> Finalize.
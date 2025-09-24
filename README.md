
# Python_Testing_Vibe: Human-in-the-Loop Document Processing System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This repository contains a robust, RAG-ready document processing pipeline with full auditability, human-in-the-loop verification, and AI integration.

## Key Features

- **End-to-end document pipeline:** Intake → OCR → AI Classification → Human Verification → Grouping → Ordering → Export
- **Full audit trail:** Every AI prompt/response, human correction, and status change is logged in the database (`interaction_log` table)
- **RAG-ready:** All OCR text, AI outputs, and human decisions are stored and queryable for future LLM workflows
- **Export:** Each document is exported as a non-searchable PDF, a searchable PDF (with OCR text layer), and a Markdown log
- **Modern Flask web UI** for mission control and review

## Prerequisites

- Python 3.x
- Git

## Setup

1. Clone this repository to your local machine.
   ```sh
   git clone <your-repository-url>
   cd Python_Testing_Vibe
   ```
2. Create and activate a virtual environment.
   ```sh
   python -m venv venv
   source venv/bin/activate
   ```
3. Install the required dependencies.
   ```sh
   pip install -r requirements.txt
   ```
4. Initialize the database:
   ```sh
   python doc_processor/dev_tools/database_setup.py
   ```
5. Configure `.env` (see `.env.sample` for options)

## Usage

1. Start the Flask server:
   ```sh
   python doc_processor/app.py
   ```
2. Access the UI at `http://localhost:5000`
3. Place test PDFs in your configured INTAKE_DIR
4. Follow the Mission Control workflow for processing, verification, grouping, ordering, and export

## Audit & RAG Integration

- All document/page-level OCR text is stored in the database for retrieval
- The `interaction_log` table records every AI and human action, correction, and status change, with batch/document/user/timestamp context
- This enables future LLMs to use Retrieval-Augmented Generation (RAG) with full process history and human feedback

## Contributing

Contributions are welcome! If you'd like to add new features or improve the workflow, feel free to submit a pull request.

## License

This repository is licensed under the MIT License.

## Credits

- @TaintedHorizon (Maintainer)

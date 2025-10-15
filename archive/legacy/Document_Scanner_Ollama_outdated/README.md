# AI Document Processor (Ollama Version)

This script automates the processing of scanned PDF documents using a locally-run Large Language Model (LLM) powered by Ollama. It monitors an intake folder, merges multiple scans, performs OCR, and uses a 2-step AI process to intelligently group documents and sort their pages.

## File Descriptions

- `document_processor.py`: The main executable script that runs the entire processing pipeline.
- `config.py`: A centralized configuration file for all settings, including directory paths, AI model selection, and logging levels. **This is the primary file you need to edit.**
- `prompts.py`: Contains the detailed instructions (prompts) that are sent to the Ollama LLM for document grouping and page ordering.
- `requirements.txt`: A list of all the Python libraries required to run the script.
- `run_scanner.sh`: A simple bash script to activate the Python virtual environment and run the main processor. This is useful for scheduling with cron.
- `README.md`: This file, providing setup and usage instructions.

## Features

- **Local & Private**: All AI processing is done locally via Ollama, ensuring your data remains private and secure.
- **Batch Processing**: Automatically merges multiple PDF files in the intake folder into a single batch for comprehensive, context-aware analysis.
- **AI-Powered Grouping**: An initial AI call analyzes the entire batch to group pages into distinct logical documents (e.g., invoices, boarding passes, multi-page packets).
- **AI-Powered Ordering**: A second, focused AI call is made for each logical document to determine the correct page order, which is crucial for handling pages scanned out of sequence.
- **Automated Filing**: For each identified document, the script creates a searchable OCR'd PDF and a Markdown analysis report, then files them into pre-defined category folders.
- **Scheduled Runs**: Includes a launcher script (`run_scanner.sh`) for easy automation and scheduling with tools like cron.

## Workflow

The script follows these steps during a run:

1.  **Scan Intake**: Checks the `INTAKE_DIR` for any new PDF files.
2.  **Merge**: If multiple PDFs are found, they are merged into a single temporary "mega-batch" PDF.
3.  **OCR**: The script performs OCR on the entire batch PDF to extract all text content. It also creates a new, text-searchable version of the PDF.
4.  **AI Grouping**: The full extracted text is sent to the Ollama LLM with a specialized prompt, asking it to identify logical document groups and assign a category and title to each.
5.  **AI Ordering**: For each group identified by the AI, the script sends the text for just those pages back to the LLM with a second prompt, asking it to determine the correct page order.
6.  **Split**: The script splits the OCR'd mega-batch PDF into separate, smaller PDFs based on the groups and page order determined by the AI.
7.  **Final Processing**: Each small PDF is processed individually:
    *   It's moved to the correct category subfolder in `PROCESSED_DIR`.
    *   It's renamed using a standard format: `Category_Title_Timestamp.pdf`.
    *   A final, searchable OCR copy is saved alongside it.
    *   A Markdown (`.md`) file is created containing a report of the analysis.
8.  **Archive & Cleanup**: The original files from the intake directory are moved to the `ARCHIVE_DIR`, and all temporary files are deleted.

## Prerequisites

Before setting up the script, you need to have the following installed on your system:

1.  **Python 3.8+**
2.  **Tesseract OCR Engine**: The script relies on Tesseract for text extraction.
    ```bash
    sudo apt update && sudo apt install tesseract-ocr -y
    ```
3.  **Ollama**: The engine for running the local LLM.
    ```bash
    curl -fsSL https://ollama.com/install.sh | sh
    ```

## Setup Instructions

1.  **Create Project Folder**:
    Place all the project files into a single directory, for example: `/home/user/doc_scanner/`.

2.  **Create Virtual Environment**:
    Navigate to your project directory and create a Python virtual environment to isolate dependencies.
    ```bash
    cd /path/to/your/project
    python3 -m venv .venv
    ```

3.  **Activate Environment**:
    You must activate the environment before installing packages or running the script.
    ```bash
    source .venv/bin/activate
    ```

4.  **Install Python Dependencies**:
    Install all required libraries from the `requirements.txt` file.
    ```bash
    pip install -r requirements.txt
    ```

5.  **Download an Ollama Model**:
    Pull the model you wish to use. `llama3.1:8b` is a powerful and recommended choice that works well for this task.
    ```bash
    ollama pull llama3.1:8b
    ```

6.  **Configure `config.py`**:
    This is the most important step. Open `config.py` and carefully edit the variables:
    - `OLLAMA_HOST`: Set this to the IP address of the machine running Ollama.
    - `OLLAMA_MODEL`: Ensure this matches the model you downloaded (e.g., `"llama3.1:8b"`).
    - `INTAKE_DIR` and `PROCESSED_DIR`: Set these to the absolute paths of your intake and processed documents folders.

7.  **Make Launcher Executable**:
    Grant execute permissions to the launcher script.
    ```bash
    chmod +x run_scanner.sh
    ```

## Usage

### Manual Run

To process documents immediately, navigate to the project directory, activate the virtual environment, and run the Python script directly:

```bash
cd /path/to/your/project
source .venv/bin/activate
python document_processor.py
```

### Automated Run with Cron

To run the scanner automatically on a schedule (e.g., every 15 minutes), you can add a cron job.

1.  Open your crontab for editing:
    ```bash
    crontab -e
    ```
2.  Add the following line, making sure to **use the absolute path** to your `run_scanner.sh` script:
    ```
    */15 * * * * /path/to/your/project/run_scanner.sh
    ```
This will execute the script every 15 minutes, processing any new files in the intake directory.

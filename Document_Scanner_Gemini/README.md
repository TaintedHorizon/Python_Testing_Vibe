# AI Document Processor (Gemini Version)

This script automates the processing of scanned PDF documents using the Google Gemini API. It monitors an intake folder, merges multiple scans, performs OCR, and uses a 2-step AI process to intelligently group documents and sort their pages before filing them away.

## File Descriptions

- `document_processor.py`: The main executable script that runs the entire processing pipeline.
- `config.py`: A centralized configuration file for all settings, including directory paths and logging levels. **This is the primary file you need to edit.**
- `config.py.sample`: A template to use for creating your `config.py` file.
- `prompts.py`: Contains the detailed instructions (prompts) that are sent to the Gemini API for document grouping and page ordering.
- `requirements.txt`: A list of all the Python libraries required to run the script.
- `run_scanner.sh`: A simple bash script to set the API key from a `.env` file, activate the Python virtual environment, and run the main processor. This is the recommended way to run the script, especially for scheduling.
- `README.md`: This file, providing setup and usage instructions.

## Features

- **Cloud-Powered AI**: Leverages the Google Gemini API for state-of-the-art document analysis.
- **Batch Processing**: Automatically merges multiple PDF files in the intake folder into a single batch for comprehensive, context-aware analysis.
- **AI-Powered Grouping**: An initial AI call analyzes the entire batch to group pages into distinct logical documents (e.g., invoices, boarding passes, multi-page packets).
- **AI-Powered Ordering**: A second, focused AI call is made for each logical document to determine the correct page order, which is crucial for handling pages scanned out of sequence.
- **Structured JSON Output**: Uses Gemini's JSON mode to ensure reliable, machine-readable responses from the API.
- **Automated Filing**: For each identified document, the script creates a searchable OCR'd PDF and a Markdown analysis report, then files them into pre-defined category folders.
- **Secure API Key Handling**: Loads the Gemini API key from an environment variable or a `.env` file for better security.
- **Scheduled Runs**: The `run_scanner.sh` script is designed for easy automation and scheduling with tools like cron.

## Workflow

The script follows these steps during a run:

1.  **Scan Intake**: Checks the `INTAKE_DIR` for any new PDF files.
2.  **Merge**: If multiple PDFs are found, they are merged into a single temporary "mega-batch" PDF.
3.  **OCR**: The script performs OCR on the entire batch PDF to extract all text content. It also creates a new, text-searchable version of the PDF.
4.  **AI Grouping (API Call #1)**: The full extracted text is sent to the Gemini API with a specialized prompt, asking it to identify logical document groups and assign a category and title to each.
5.  **AI Ordering (API Call #2)**: For each group identified by the AI, the script sends the text for just those pages back to the API with a second prompt, asking it to determine the correct page order.
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
3.  **A Google Gemini API Key**: You can obtain a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey).

## Setup Instructions

1.  **Clone or Download Files**:
    Place all the project files into a single directory, for example: `/home/user/doc_scanner_gemini/`.

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

5.  **Set Up API Key**:
    Create a file named `.env` in your project directory. This file will securely store your API key.
    ```bash
    echo "GEMINI_API_KEY=YOUR_API_KEY_HERE" > .env
    ```
    Replace `YOUR_API_KEY_HERE` with your actual Gemini API key.

6.  **Configure `config.py`**:
    - Rename `config.py.sample` to `config.py`.
    - Open `config.py` and carefully edit the directory paths (`INTAKE_DIR`, `PROCESSED_DIR`) to match the locations on your system.

7.  **Make Launcher Executable**:
    Grant execute permissions to the launcher script.
    ```bash
    chmod +x run_scanner.sh
    ```

## Usage

### Manual Run

To process documents immediately, simply execute the launcher script. It will handle setting the environment variable, activating the virtual environment, and running the Python script.

```bash
./run_scanner.sh
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

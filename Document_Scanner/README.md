# Document Scanner and Processor

This script automates the processing, categorization, and archiving of PDF documents. It monitors an intake directory for new PDF files, performs Optical Character Recognition (OCR) on them, uses a Google Gemini AI model to classify the documents into predefined categories, generates human-readable titles, and then renames and moves the processed documents to their respective category folders.

## Features

*   **Automated Monitoring:** Watches a specified intake directory for new PDF files.
*   **OCR Integration:** Uses `pytesseract` to extract text from scanned, image-based PDFs.
*   **AI-Powered Categorization:** Leverages the Google Gemini API to analyze document text and assign a category and a concise title.
*   **Two-Step AI Analysis:**
    1.  **Grouping:** A primary AI call groups pages into logical document "packets" based on their content.
    2.  **Ordering:** A secondary, focused AI call determines the correct page order for each packet.
*   **Intelligent File Naming:** Renames files using a clean, human-readable format based on the AI's analysis (`category_title_timestamp.pdf`).
*   **Detailed Reporting:** For each processed document, it generates a Markdown file containing the extracted text and a summary of the AI's analysis.
*   **Searchable PDFs:** Creates an OCR'd copy of each document, embedding the extracted text as a searchable layer.
*   **Archiving:** Moves the original, unprocessed files to an archive directory for a configurable retention period.
*   **Dry Run Mode:** Allows you to test the script's logic without making any actual changes to your files.

## How It Works

1.  **Scan Intake Directory:** The script scans the `INTAKE_DIR` for any PDF files.
2.  **Perform OCR:** For each PDF, it performs OCR to extract all text content. If a page already has text, it uses that; otherwise, it renders the page as an image and uses Tesseract to extract the text.
3.  **Analyze and Group (AI Call #1):** The full extracted text is sent to the Gemini AI model. The AI's task is to identify logical document groups (or "packets") within the pages and assign a `category` and `title` to each group.
4.  **Determine Page Order (AI Call #2):** For each group identified, a second, more focused AI call is made. This call's sole purpose is to determine the correct reading order of the pages within that group.
5.  **Split the PDF:** The original PDF is split into temporary PDF files, one for each logical document, with the pages arranged in the correct order.
6.  **Process and Archive:** Each temporary PDF is then processed:
    *   It's moved to the appropriate category subfolder in `PROCESSED_DIR`.
    *   It's renamed based on its category and title.
    *   A searchable OCR copy is saved alongside it.
    *   A Markdown report is generated.
7.  **Cleanup:** The original intake file is moved to the `ARCHIVE_DIR`, and any temporary files are deleted.

## File Descriptions

*   **`document_processor.py`**: The main executable script that contains all the logic for processing the documents.
*   **`config.py`**: This file contains user-specific configuration settings for the script. It is now tracked by Git as it no longer contains sensitive information. Users should modify this file to suit their local environment.
*   **`config.py.sample`**: This file is a template for `config.py`. It contains configuration settings for the document processing script. To use it, rename this file to `config.py` and fill in your specific details.
*   **`prompts.py`**: Contains the system prompts used for interacting with the AI model, externalized for clarity and easier management.
*   **`requirements.txt`**: A list of the Python libraries required to run the script.

## Setup and Usage

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/TaintedHorizon/Python_Testing_Vibe.git
    cd Python_Testing_Vibe/Document_Scanner
    ```

2.  **Install dependencies:**
    *   **Tesseract OCR Engine:** This script requires Tesseract to be installed on your system. You can find installation instructions here: [Tesseract Documentation](https://tesseract-ocr.github.io/tessdoc/Installation.html)
    *   **Python Libraries:** Install the required Python packages using pip:
        ```bash
        pip install -r requirements.txt
        ```

3.  **Configure the script:**
    *   **Set your Google Gemini API Key:** The script now securely loads the API key from an environment variable. Set `GEMINI_API_KEY` in your environment before running the script:
        ```bash
        export GEMINI_API_KEY="YOUR_GOOGLE_GEMINI_API_KEY"
        # For Windows, use: set GEMINI_API_KEY="YOUR_GOOGLE_GEMINI_API_KEY"
        ```
    *   Rename `config.py.sample` to `config.py`.
    *   Open `config.py` and set the following variables:
        *   `INTAKE_DIR`: The absolute path to the directory where you will place new scans.
        *   `PROCESSED_DIR`: The absolute path to the directory where categorized documents will be saved.
        *   `ARCHIVE_DIR`: The absolute path to the directory where original files will be archived.
        *   `DRY_RUN`: Set to `False` to enable file operations.

4.  **Run the script:**
    ```bash
    python document_processor.py
    ```

## Configuration

All configuration is handled in the `config.py` file, except for the API key.

*   **`API_URL`**: The endpoint for the Gemini model. The default is `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent`.
*   **`DRY_RUN`**: `True` or `False`. If `True`, no files will be moved or saved.
*   **`INTAKE_DIR`**: Path to your intake/scans folder.
*   **`PROCESSED_DIR`**: Path to where the processed and categorized files will be saved.
*   **`CATEGORIES`**: A dictionary mapping categories to subfolder names.
*   **`LOG_FILE`**: Path to the log file.
*   **`LOG_LEVEL`**: The logging level (e.g., `INFO`, `DEBUG`).
*   **`ARCHIVE_DIR`**: Path to where original files are archived after processing.
*   **`ARCHIVE_RETENTION_DAYS`**: How long to keep files in the archive.
*   **`MAX_RETRIES`**: The number of times to retry a failed API call.
*   **`RETRY_DELAY_SECONDS`**: The delay between retries.

## Dependencies

*   **`google-generativeai`**: To interact with the Google Gemini API.
*   **`PyMuPDF`**: For PDF manipulation (splitting, creating searchable text layers).
*   **`pytesseract`**: For performing OCR on image-based PDFs.
*   **`Pillow`**: An imaging library required by `pytesseract`.
*   **`requests`**: For making HTTP requests to the Gemini API.

## Logging

The script generates a log file (`document_processor.log` by default) that records its operations, including which files are processed, the results of the AI analysis, and any errors that occur.

## Dry Run Mode

By setting `DRY_RUN = True` in `config.py`, the script will run through its entire logic—including OCR and AI analysis—but will not move, save, or delete any files. Log messages will indicate what action *would* have been taken. This is highly recommended for initial setup and testing.
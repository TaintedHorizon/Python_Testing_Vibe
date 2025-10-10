# document_processor.py (Definitive AI Pipeline Version)
#
# This script implements a sophisticated, multi-stage pipeline for processing PDF documents.
# It automates the classification, organization, and archiving of scanned or digital documents
# by leveraging Optical Character Recognition (OCR) and a locally-run Large Language Model (LLM).
#
# The pipeline is designed for robustness and clarity, following these core steps:
# 1. OCR with EasyOCR: Extracts text from each page of the input PDFs. EasyOCR is chosen for its
#    high accuracy and its ability to cache recognition models locally, which speeds up subsequent runs.
# 2. Per-Page Classification: A lightweight AI call is made for each page to determine its category
#    based on its content. This individual classification is fast and allows for fine-grained sorting.
# 3. Smart Grouping: The script uses Python logic to group consecutive pages that have been assigned
#    the same category, effectively identifying individual logical documents within a larger batch scan.
# 4. Focused AI Analysis: For each identified document group, more intensive AI calls are made to:
#    a. Generate a descriptive title.
#    b. Determine the correct reading order of the pages, correcting for scanning errors.
# 5. File Organization: The script creates final, searchable PDF files and markdown reports,
#    organizing them into a structured directory system based on their category.
# 6. Logging and Archiving: Detailed logs provide a clear record of the entire process, and
#    original files are archived for auditing and backup purposes.

# --- Standard Library Imports ---
import os # Provides functions for interacting with the operating system, like file paths and directory creation.
import shutil # Offers high-level file operations, such as copying and moving files.
import fitz  # PyMuPDF - A powerful library for working with PDF documents. Used for opening, reading, and manipulating PDFs.
import json # For working with JSON data, particularly for parsing AI model responses.
import time # Provides time-related functions, used here for introducing delays in retry mechanisms.
import io # Core tools for working with I/O streams, used for handling image data in memory.
import re # Regular expression operations, used for pattern matching in text extraction and page ordering.
from datetime import datetime, timedelta # Classes for working with dates and times, used for archiving and retention policies.
from PIL import Image # Python Imaging Library (Pillow) - Used for image manipulation, especially for OCR preprocessing.
import logging # Flexible event logging system for tracking script execution, debugging, and status updates. 

# --- Suppress Specific Warnings ---
import warnings
# This will hide the specific "pin_memory" UserWarning from EasyOCR/PyTorch when no GPU is found.
# It does NOT disable GPU acceleration if a GPU is available.
warnings.filterwarnings(
    "ignore", 
    message=".*'pin_memory' argument is set as true but no accelerator is found.*"
)

# --- Third-Party Library Imports ---
import ollama # Client library for interacting with Ollama, a platform for running large language models locally.
import easyocr # Optical Character Recognition (OCR) library, used for extracting text from images within PDFs.
import pytesseract # Python wrapper for Google's Tesseract-OCR Engine, used for orientation detection in images.

# --- Project-Specific Imports ---
# Imports prompt templates from a local 'prompts.py' file. These templates define the structure
# of the prompts sent to the Ollama language model for classification, titling, and ordering tasks.
from prompts import CLASSIFICATION_PROMPT_TEMPLATE, TITLING_PROMPT_TEMPLATE, ORDERING_PROMPT

# --- Environment and Configuration ---
# This block attempts to import configuration variables from 'config.py'.
# 'config.py' is expected to contain essential settings for the script's operation,
# such as directory paths, Ollama model details, category definitions, and logging settings.
# If 'config.py' is not found or critical variables are missing, the script will log
# a critical error and exit, as it cannot proceed without these settings. 
try:
    # Attempt to import all necessary configuration variables from the 'config.py' file.
    # This centralized configuration approach makes the script easier to manage and adapt
    # to different environments without modifying the core logic. 
    from config import (
        DRY_RUN, OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_CONTEXT_WINDOW,
        INTAKE_DIR, PROCESSED_DIR, CATEGORIES, LOG_FILE, LOG_LEVEL,
        ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS, MAX_RETRIES, RETRY_DELAY_SECONDS
    )
except ImportError:
    # If the 'config.py' file itself cannot be found, it's a fatal error.
    # The script prints a message to standard output and exits because logging may not be configured yet. 
    print("CRITICAL ERROR: The 'config.py' file was not found. This file is essential for script operation. Please create it from 'config.py.sample'.")
    exit(1)
except Exception as e:
    # This catches other potential errors during import, such as a syntax error within config.py
    # or if a variable is referenced before it's assigned within that file. 
    print(f"CRITICAL ERROR: An unexpected error occurred while loading configuration from 'config.py': {e}")
    exit(1)


# --- Logging Setup ---
# Logging is configured here, immediately after imports and configuration loading.
# This ensures that all subsequent actions, including library initializations, can be logged.
# Placing this setup early prevents other libraries (like EasyOCR) from establishing their own, 
# potentially conflicting, default logging configurations.

# A constant template for creating clear markers between pages in the consolidated text.
# This helps the LLM distinguish between pages when processing a multi-page document. 
PAGE_MARKER_TEMPLATE = "\n\n--- Page {} ---\n\n"

# Maps the string-based log level from the config file (e.g., "INFO", "DEBUG")
# to the corresponding constant required by the logging library (e.g., logging.INFO). 
log_level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

# Configures the root logger for the entire application. 
logging.basicConfig(
    # Sets the minimum level of messages to be processed. Messages with a lower severity will be ignored. 
    # It defaults to INFO if the specified LOG_LEVEL is invalid. 
    level=log_level_map.get(LOG_LEVEL.upper(), logging.INFO),

    # Defines the format for every log message. 
    # Example: "2023-10-27 10:30:00,123 - INFO - This is a log message." 
    format='%(asctime)s - %(levelname)s - %(message)s',

    # Specifies where the log messages should be sent. 
    handlers=[
        # A FileHandler is added only if a LOG_FILE path is provided in the config. 
        # This sends log messages to the specified file. 
        logging.FileHandler(LOG_FILE) if LOG_FILE else logging.NullHandler(),

        # A StreamHandler is always included to ensure logs are also printed to the console (stderr). 
        # This provides real-time feedback during script execution. 
        logging.StreamHandler()
    ]
)


# --- Initialize External Services ---
# This section prepares the clients for the two main external services this script relies on: 
# 1. Ollama: For running the Large Language Model (LLM) that performs classification, titling, and ordering. 
# 2. EasyOCR: For performing Optical Character Recognition to extract text from images and scanned PDFs. 
# Initialization is performed upfront to fail fast if these critical services are not available. 

# Initialize the Ollama client. 
try:
    # Creates an instance of the Ollama client, configured to connect to the host
    # specified in the config file. This establishes the connection for all subsequent LLM calls. 
    ollama_client = ollama.Client(host=OLLAMA_HOST)
    logging.info(f"Successfully connected to Ollama client at host: {OLLAMA_HOST}")
except Exception as e:
    # If the client cannot be initialized (e.g., the Ollama service is not running, the host is incorrect, 
    # or there's a network issue), a critical error is logged, and the script terminates. 
    logging.critical(f"Failed to create Ollama client for host '{OLLAMA_HOST}'. Is the Ollama service running and accessible? Error: {e}")
    exit(1)

# Initialize the EasyOCR reader. 
try:
    logging.info("Initializing EasyOCR reader... This may take a moment on the first run as models are downloaded.")
    # Define a permanent, local directory for EasyOCR to store its language models. 
    # This prevents re-downloading the models on every script run, significantly speeding up initialization. 
    model_cache_dir = os.path.join(os.path.dirname(__file__), "model_cache")
    os.makedirs(model_cache_dir, exist_ok=True) # Create the directory if it doesn't exist. 

    # Initialize the EasyOCR reader for the English language ('en'). 
    # The `model_storage_directory` parameter directs EasyOCR to use our specified cache directory. 
    ocr_reader = easyocr.Reader(['en'], model_storage_directory=model_cache_dir)
    logging.info("EasyOCR reader initialized successfully.")
except Exception as e:
    # If EasyOCR fails to initialize (e.g., due to missing system dependencies, model download failures, 
    # or permissions issues), a critical error is logged, and the script terminates. 
    logging.critical(f"Failed to initialize EasyOCR. Please check for missing dependencies or model download issues. Error: {e}")
    exit(1)


# --- Path and Directory Setup ---
# This section ensures that the necessary directory structure for processed files and archives exists. 
# It reads the base paths from the config and creates the full, absolute paths for each category. 

# Create a dictionary mapping category names to their full, absolute directory paths. 
# This is derived from the `CATEGORIES` dictionary in `config.py`. 
# Example: If PROCESSED_DIR is "/data/processed" and CATEGORIES is {"invoices": "finance/invoices"},
# this will create an entry: {"invoices": "/data/processed/finance/invoices"}. 
ABSOLUTE_CATEGORIES = {
    category_name: os.path.join(PROCESSED_DIR, relative_path)
    for category_name, relative_path in CATEGORIES.items()
}

# Iterate through the absolute paths and create the physical directories on the filesystem. 
# `exist_ok=True` prevents an error if the directory already exists. 
for category_path in ABSOLUTE_CATEGORIES.values():
    os.makedirs(category_path, exist_ok=True)

# Also ensure the main archive directory exists. 
os.makedirs(ARCHIVE_DIR, exist_ok=True)
logging.info("Verified and created all necessary processing and archive directories.")


def cleanup_archive(directory: str, retention_days: int):
    """
    Deletes files in the specified archive directory that are older than the retention period.
    This function helps manage disk space by automatically removing old, archived documents.

    Args:
        directory (str): The absolute path to the archive directory to clean. 
        retention_days (int): The maximum number of days to keep a file in the archive. 
    """
    logging.info(f"Starting archive cleanup in '{directory}'. Deleting files older than {retention_days} days.")
    now = datetime.now()
    # Calculate the cutoff date. Any file modified before this date will be deleted. 
    retention_limit = now - timedelta(days=retention_days)

    try:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            # Ensure we are only checking files, not subdirectories. 
            if os.path.isfile(file_path):
                try:
                    # Get the last modification time of the file. 
                    mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    # Check if the file's modification time is older than the retention limit. 
                    if mod_time < retention_limit:
                        if DRY_RUN:
                            logging.info(f"[DRY RUN] Would have deleted old archive file: {file_path}")
                        else:
                            os.remove(file_path)
                            logging.info(f"Deleted old archive file: {file_path}")
                except Exception as e:
                    # Log an error if a specific file cannot be processed, but continue with the rest. 
                    logging.error(f"Error processing archive file '{file_path}' for cleanup: {e}")
    except Exception as e:
        # Log an error if the archive directory itself cannot be accessed. 
        logging.error(f"Failed to list files in archive directory '{directory}': {e}")

    logging.info("Archive cleanup complete.")


# --- LLM and Helper Functions ---

def classify_single_page(page_text: str) -> str:
    """
    AI Task 1: Classifies the text of a single page into one of the predefined categories. 

    This function constructs a prompt for the LLM, sending the page's text and a list of
    valid categories. It includes a retry mechanism and robust matching to handle minor
    variations in the LLM's response (e.g., singular vs. plural). 

    Args:
        page_text (str): The OCR'd text content of a single PDF page. 

    Returns:
        str: The determined category name (e.g., "invoices", "receipts", "other"). 
    """
    # Format the list of categories for inclusion in the system prompt. 
    categories_list_str = "\n".join(f"- {cat}" for cat in CATEGORIES.keys())
    # Prepare the system prompt using a template, instructing the AI on its task. 
    system_prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(categories_list=categories_list_str)

    # Structure the request for the Ollama API. 
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': page_text}
    ]
    # Set model-specific options. `num_ctx` defines the context window size. 
    try:
        env_num = os.getenv('OLLAMA_NUM_GPU')
        num_gpu_val = int(env_num) if env_num is not None else 0
    except Exception:
        num_gpu_val = 0
    options = {'num_ctx': 4096, 'num_gpu': num_gpu_val}

    # Implement a retry loop to handle transient network or model errors. 
    for attempt in range(MAX_RETRIES):
        try:
            # Send the request to the Ollama model. 
            response = ollama_client.chat(model=OLLAMA_MODEL, messages=messages, options=options)
            # Extract, clean, and standardize the category from the AI's response. 
            category = response['message']['content'].strip().lower().replace(" ", "_")

            # First, check for an exact match with the defined categories. 
            if category in CATEGORIES:
                return category
            else:
                # If no exact match, try a more flexible match. This handles cases where the AI
                # might return "invoice" instead of "invoices". It checks if the AI's response
                # starts with a known category key (stripping the 's' for simple pluralization). 
                for key in CATEGORIES:
                    if category.startswith(key.lower().replace(" ", "_").rstrip('s')):
                        logging.warning(f"AI returned a non-standard category '{category}', but it was successfully matched to '{key}'.")
                        return key

                # If no match is found, log a warning and default to the 'other' category. 
                logging.warning(f"AI returned an unknown or ambiguous category '{category}'. Defaulting to 'other'.")
                return "other"
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES} for single-page classification failed: {e}")
            # Wait before retrying to avoid overwhelming the service. 
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)

    # If all retries fail, return 'other' as a fallback. 
    logging.error("All retry attempts for page classification failed. Defaulting to 'other'.")
    return "other"


def generate_title_for_group(group_text: str, category: str) -> str:
    """
    AI Task 2: Generates a concise, descriptive title for a group of pages. 

    This function sends the combined text of a document group to the LLM and asks it
    to create a suitable filename-friendly title based on the content and category. 

    Args:
        group_text (str): The concatenated text of all pages in the document group. 
        category (str): The category assigned to this document group. 

    Returns:
        str: A clean, descriptive title for the document. 
    """
    # Prepare the system prompt, providing context (the document's category) to the AI. 
    system_prompt = TITLING_PROMPT_TEMPLATE.format(category=category)
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': group_text}
    ]
    # Use the full context window for better title generation. 
    try:
        env_num = os.getenv('OLLAMA_NUM_GPU')
        num_gpu_val = int(env_num) if env_num is not None else 0
    except Exception:
        num_gpu_val = 0
    options = {'num_ctx': OLLAMA_CONTEXT_WINDOW, 'num_gpu': num_gpu_val}

    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Generating title for a document in the '{category}' category...")
            response = ollama_client.chat(model=OLLAMA_MODEL, messages=messages, options=options)
            # Return the cleaned-up title from the AI's response. 
            return response['message']['content'].strip()
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES} for title generation failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)

    # If all retries fail, return a generic title. 
    logging.error("All retry attempts for title generation failed. Using a default title.")
    return "Untitled Document"


def get_correct_page_order(document_group_text: str, original_page_numbers: list[int]) -> list[int] | None:
    """
    AI Task 3: Determines the correct reading order for a set of pages. 

    This is useful for documents that may have been scanned out of order. The function sends
    the document's full text to the LLM and asks for a JSON response containing the
    correct sequence of page numbers. 

    Args:
        document_group_text (str): The concatenated text of the document group. 
        original_page_numbers (list[int]): The initial list of page numbers in the group. 

    Returns:
        list[int] | None: A list of page numbers in the correct order, or None if the
                          analysis fails or returns an invalid result. 
    """
    system_prompt = ORDERING_PROMPT
    user_query = f"Determine the correct page order for the following document text:\n\n{document_group_text}"
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_query}
    ]
    try:
        env_num = os.getenv('OLLAMA_NUM_GPU')
        num_gpu_val = int(env_num) if env_num is not None else 0
    except Exception:
        num_gpu_val = 0
    options = {'num_ctx': OLLAMA_CONTEXT_WINDOW, 'num_gpu': num_gpu_val}

    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Requesting page order analysis from Ollama model '{OLLAMA_MODEL}' (Attempt {attempt + 1})...")
            # Request JSON output format from the model. 
            response = ollama_client.chat(model=OLLAMA_MODEL, messages=messages, format='json', options=options)
            response_content = response['message']['content']
            logging.debug(f"Raw Ollama ordering response content:\n---\n{response_content}\n---")

            # Parse the JSON response to extract the page order. 
            page_order_data = json.loads(response_content).get("page_order")

            if page_order_data and isinstance(page_order_data, list):
                clean_order: list[int] = []
                # Sanitize the list from the AI, which might contain strings like "Page 1". 
                for item in page_order_data:
                    if isinstance(item, int):
                        clean_order.append(item)
                    elif isinstance(item, str):
                        # Use regex to find the first number in a string. 
                        match = re.search(r'\d+', item)
                        if match:
                            clean_order.append(int(match.group(0)))

                # Final validation: ensure the returned page numbers were part of the original document. 
                # This prevents the AI from hallucinating page numbers that don't exist. 
                validated_order = [p for p in clean_order if p in original_page_numbers]
                if len(validated_order) == len(original_page_numbers):
                    logging.info(f"Successfully determined page order: {validated_order}")
                    return validated_order
                else:
                    logging.warning(f"AI returned an incomplete or invalid page order. Original: {original_page_numbers}, AI returned: {validated_order}. Falling back to original order.")
                    return original_page_numbers # Fallback to original if validation fails

            logging.warning("AI response for page order was empty or not a list. Falling back to original order.")
            return original_page_numbers # Fallback to original order
        except json.JSONDecodeError:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Failed to decode JSON from Ollama's ordering response.")
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Page ordering analysis failed: {e}")

        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY_SECONDS)

    logging.error("All retry attempts for page ordering failed. Falling back to the original page order.")
    return original_page_numbers # Fallback to original order


def get_text_for_page(full_text: str, page_number: int) -> str:
    """
    Extracts the text for a single page from the concatenated full text string. 
    It uses the PAGE_MARKER_TEMPLATE to find the content of a specific page. 

    Args:
        full_text (str): The complete text of the PDF, with pages separated by markers. 
        page_number (int): The number of the page to extract. 

    Returns:
        str: The text of the specified page, or an empty string if not found. 
    """
    # This regex looks for `--- Page {page_number} ---` and captures everything
    # until it hits the next `--- Page` marker or the end of the string (`\Z`). 
    pattern = re.compile(
        r'--- Page ' + str(page_number) + r' ---\n(.*?)(?=\n--- Page|\Z)',
        re.DOTALL  # re.DOTALL allows '.' to match newline characters. 
    )
    match = pattern.search(full_text)
    return match.group(1).strip() if match else ""


# --- PDF Processing Functions ---

def merge_pdfs(pdf_list: list[str], output_path: str) -> str | None:
    """
    Merges a list of PDF files into a single PDF document. 

    Args:
        pdf_list (list[str]): A list of absolute paths to the PDF files to merge. 
        output_path (str): The absolute path where the merged PDF will be saved. 

    Returns:
        str | None: The path to the merged PDF if successful, otherwise None. 
    """
    logging.info(f"Merging {len(pdf_list)} PDF files into '{os.path.basename(output_path)}'...")
    # Create a new, empty PDF document in memory. 
    result_pdf = fitz.open()
    try:
        for pdf_path in pdf_list:
            try:
                # Open each source PDF and append its pages to the result PDF. 
                with fitz.open(pdf_path) as pdf_doc:
                    result_pdf.insert_pdf(pdf_doc)
                logging.debug(f"Successfully appended '{os.path.basename(pdf_path)}' to the merge batch.")
            except Exception as e:
                # Log an error if a specific PDF is corrupt or cannot be opened, then skip it. 
                logging.error(f"Could not process '{pdf_path}' during merge and will be skipped. Error: {e}")

        # Save the final merged document to the specified output path. 
        result_pdf.save(output_path)
        logging.info(f"Merge complete. Output saved to: {output_path}")
        return output_path
    except Exception as e:
        logging.error(f"A critical error occurred during the PDF merge operation: {e}")
        return None
    finally:
        # Always ensure the PDF object is closed to free up resources. 
        result_pdf.close()


def perform_ocr_on_pdf(file_path: str) -> tuple[str, int]:
    """
    Performs OCR on a PDF file, page by page, and returns the full text content. 

    This function iterates through each page of the PDF. For each page, it first tries to
    extract existing text. If the page is image-based (no text), it renders the page as an
    image, performs orientation correction, and then uses EasyOCR to extract the text. 

    Args:
        file_path (str): The absolute path to the PDF file. 

    Returns:
        tuple[str, int]: A tuple containing:
                         - The full extracted text, with pages separated by markers. 
                         - The total number of pages in the document. 
    """
    page_count = 0
    full_extracted_text = ""
    doc: fitz.Document | None = None
    try:
        doc = fitz.open(file_path)
        page_count = doc.page_count
        logging.info(f"Starting OCR for '{os.path.basename(file_path)}' which has {page_count} pages.")

        # The '# type: ignore' comments are used to suppress potential false-positive warnings
        # from static analysis tools like Pylance, which can sometimes struggle with the dynamic
        # nature of libraries like PyMuPDF (fitz). 
        for i, page in enumerate(doc):  # type: ignore
            page_number = i + 1
            # Add a marker to delineate this page's content in the final text blob. 
            full_extracted_text += PAGE_MARKER_TEMPLATE.format(page_number)

            # First, try to extract text directly. This works for digitally-created PDFs. 
            current_page_text = page.get_text().strip()  # type: ignore

            # If `get_text()` returns no content, the page is likely an image. 
            if not current_page_text:
                logging.info(f"Page {page_number} contains no selectable text. Performing image-based OCR.")
                # Render the page to a high-resolution pixmap (an image object). 
                # A 2x2 matrix doubles the resolution, improving OCR accuracy. 
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.open(io.BytesIO(pix.tobytes("png")))

                # --- Orientation Correction ---
                try:
                    # Use Pytesseract's Orientation and Script Detection (OSD) to find the page's rotation. 
                    osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT)
                    rotation = osd.get('rotate', 0)
                    if rotation > 0:
                        logging.info(f"Page {page_number} appears to be rotated by {rotation} degrees. Correcting orientation.")
                        # Rotate the image to be upright. `expand=True` ensures the image resizes to fit the new dimensions. 
                        img = img.rotate(-rotation, expand=True)
                except Exception as e:
                    logging.warning(f"Could not perform orientation detection on page {page_number}. OCR will proceed with the original orientation. Error: {e}")

                # Convert the corrected PIL Image back to bytes for EasyOCR. 
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_bytes = img_byte_arr.getvalue()

                # --- Perform OCR ---
                # `detail=0` returns only the text. `paragraph=True` groups text into logical paragraphs. 
                results = ocr_reader.readtext(img_bytes, detail=0, paragraph=True)
                current_page_text = "\n".join(map(str, results))
                logging.info(f"Successfully extracted text from image on page {page_number}.")

            # Append the extracted text (either from `get_text` or OCR) to the full document text. 
            full_extracted_text += current_page_text
        return full_extracted_text, page_count
    except Exception as e:
        logging.error(f"A critical error occurred during OCR on '{file_path}': {e}")
        return "", page_count
    finally:
        # Ensure the document is closed if it was opened. 
        if doc:
            doc.close()


def create_output_files(source_pdf_path: str, category: str, title: str):
    """
    Creates the final output files for a processed document group. 

    This function takes a temporary PDF (containing one logical document), performs a final
    OCR pass to create a searchable PDF, saves a copy of the original, and generates a
    markdown report summarizing the analysis. 

    Args:
        source_pdf_path (str): Path to the temporary PDF for this document group. 
        category (str): The category assigned to the document. 
        title (str): The AI-generated title for the document. 
    """
    file_name = os.path.basename(source_pdf_path)
    logging.info(f"Creating final output files for '{file_name}' -> Category: {category}, Title: '{title}'")

    text_for_report = ""
    ocr_doc_obj = None
    doc: fitz.Document | None = None
    reason = "Success"

    try:
        # This block re-processes the temporary PDF to create two things:
        # 1. `text_for_report`: A clean text blob for the markdown file. 
        # 2. `ocr_doc_obj`: A new, searchable PDF with an invisible text layer. 
        doc = fitz.open(source_pdf_path)
        ocr_doc_obj = fitz.open()  # The new searchable PDF. 

        for page in doc:  # type: ignore
            # Repeat the OCR logic from `perform_ocr_on_pdf` to get the text for this page. 
            page_text = page.get_text().strip()  # type: ignore
            if not page_text:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # type: ignore
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                try:
                    osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT)
                    rotation = osd.get('rotate', 0)
                    if rotation > 0:
                        img = img.rotate(-rotation, expand=True)
                except Exception as e:
                    logging.warning(f"Could not perform orientation detection on final page: {e}")

                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_bytes = img_byte_arr.getvalue()
                results = ocr_reader.readtext(img_bytes, detail=0, paragraph=True)
                page_text = "\n".join(map(str, results))

            text_for_report += page_text + "\n\n"

            # Create a new page in the output searchable PDF. 
            new_page = ocr_doc_obj.new_page(width=page.rect.width, height=page.rect.height)  # type: ignore
            # Insert the original page image. 
            pix = page.get_pixmap()  # type: ignore
            new_page.insert_image(new_page.rect, stream=io.BytesIO(pix.tobytes("png")))
            # Add the OCR'd text as an invisible layer (`render_mode=3`). This makes the text selectable and searchable. 
            new_page.insert_text(page.rect.tl, page_text, render_mode=3)

        logging.info(f"Successfully created searchable text layer for '{file_name}'.")

    except Exception as e:
        logging.error(f"Error during final OCR pass for '{file_name}': {e}")
        reason = f"Final OCR pass failed due to: {e}"
    finally:
        if doc:
            doc.close()

    # --- File Naming and Saving ---
    # Sanitize the AI-generated title to create a valid filename. 
    sanitized_title = "".join(c for c in title if c.isalnum() or c in (' ', '.', '-', '_', '(', ')')).rstrip().replace(' ', '_')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Construct the base filename, e.g., "invoices_Client-A-Invoice_20231027_103000". 
    new_name_base = f"{category}_{sanitized_title}_{timestamp}"

    # Determine the final destination directory based on the category. 
    destination_dir = ABSOLUTE_CATEGORIES.get(category, ABSOLUTE_CATEGORIES["other"])
    os.makedirs(destination_dir, exist_ok=True)

    # Define the full paths for all three output files. 
    original_copy_path = os.path.join(destination_dir, f"{new_name_base}.pdf")
    ocr_copy_path = os.path.join(destination_dir, f"{new_name_base}_ocr.pdf")
    markdown_path = os.path.join(destination_dir, f"{new_name_base}.md")

    try:
        if DRY_RUN:
            logging.info(f"[DRY RUN] Would create the following files in '{destination_dir}':")
            logging.info(f"[DRY RUN]   - {os.path.basename(original_copy_path)}")
            logging.info(f"[DRY RUN]   - {os.path.basename(ocr_copy_path)}")
            logging.info(f"[DRY RUN]   - {os.path.basename(markdown_path)}")
        else:
            # 1. Save a copy of the original, unaltered segment of the PDF. 
            shutil.copy2(source_pdf_path, original_copy_path)
            logging.info(f"Saved original document segment to: {original_copy_path}")

            # 2. Save the new PDF with the searchable text layer. 
            if ocr_doc_obj:
                # `garbage=4` and `deflate=True` help to clean up and compress the PDF. 
                ocr_doc_obj.save(ocr_copy_path, garbage=4, deflate=True)
                logging.info(f"Saved searchable OCR copy to: {ocr_copy_path}")

            # 3. Create and save the markdown report. 
            markdown_content = f"""# Document Analysis Report

## Source File: {file_name}
## Assigned Category: {category}
## Assigned Title: {title}

---

## Extracted Text (OCR)

```
{text_for_report.strip()}
```

---

## Processing Summary
- **Status:** {reason}
"""
            with open(markdown_path, "w", encoding="utf-8") as md_file:
                md_file.write(markdown_content)
            logging.info(f"Saved Markdown analysis report to: {markdown_path}")

    except Exception as e:
        logging.error(f"Error saving final output files for '{file_name}': {e}")
    finally:
        # Ensure the new PDF object is closed. 
        if ocr_doc_obj:
            ocr_doc_obj.close()


def split_and_process_pdf(original_pdf_path: str, final_documents: list[dict]):
    """
    Splits the source PDF into temporary files based on document groups and processes each one. 

    This function orchestrates the final stage. It takes the logical document groups
    (defined by category, title, and page order) and creates a separate temporary PDF for
    each one. It then calls `create_output_files` to generate the final outputs for that document. 

    Args:
        original_pdf_path (str): The path to the (potentially merged) source PDF. 
        final_documents (list[dict]): A list of dictionaries, each representing a logical document. 

    Returns:
        list[str]: A list of paths to the temporary files created, for later cleanup. 
    """
    temp_files_to_clean = []
    original_doc: fitz.Document | None = None
    try:
        # Open the main source PDF once. 
        original_doc = fitz.open(original_pdf_path)

        for i, doc_details in enumerate(final_documents):
            pages_to_include = doc_details.get('page_order', [])
            category = doc_details.get('category')
            title = doc_details.get('title')

            # Basic validation to ensure the document group is well-formed. 
            if not all([pages_to_include, category, title]):
                logging.warning(f"Skipping incomplete document group #{i+1}. Details: {doc_details}")
                continue

            logging.info(f"Processing document group #{i+1}: Category='{category}', Title='{title}', Pages={pages_to_include}")

            # Create a new, empty PDF in memory for this specific document group. 
            new_doc = fitz.open()
            # Convert to 0-based index for PyMuPDF. 
            zero_indexed_pages = [p - 1 for p in pages_to_include]

            # Insert the correct pages from the original document into the new document. 
            for page_num in zero_indexed_pages:
                if 0 <= page_num < original_doc.page_count:
                    new_doc.insert_pdf(original_doc, from_page=page_num, to_page=page_num)

            # Define a unique name for the temporary split file. 
            temp_pdf_path = os.path.join(
                os.path.dirname(original_pdf_path),
                f"temp_split_{i}_{os.path.basename(original_pdf_path)}"
            )
            new_doc.save(temp_pdf_path)
            new_doc.close()
            temp_files_to_clean.append(temp_pdf_path)

            # Now, process this temporary file to create the final outputs. 
            create_output_files(temp_pdf_path, category, title) # type: ignore

        return temp_files_to_clean
    except Exception as e:
        logging.error(f"A critical error occurred during the PDF splitting and processing stage for '{original_pdf_path}': {e}")
        return temp_files_to_clean
    finally:
        if original_doc:
            original_doc.close()


# --- Main Execution Logic ---
def main():
    """
    The main function that orchestrates the entire AI document processing pipeline. 
    It follows a clear, multi-stage process to ensure clarity and robustness. 
    """
    logging.info("\n" + "="*60 + "\n========== STARTING NEW DOCUMENT PROCESSING RUN ==========\n" + "="*60)

    # Start by cleaning up the archive to manage disk space. 
    cleanup_archive(ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS)

    # --- STAGE 1 of 5: Preparing Batch File ---
    logging.info("--- STAGE 1 of 5: Preparing Batch File ---")
    # Find all PDF files in the intake directory. 
    try:
        initial_files = [
            os.path.join(INTAKE_DIR, f)
            for f in os.listdir(INTAKE_DIR)
            if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(INTAKE_DIR, f))
        ]
    except FileNotFoundError:
        logging.critical(f"The intake directory '{INTAKE_DIR}' does not exist. Halting.")
        return

    if not initial_files:
        logging.info("No new PDF files found in the intake directory. Scan complete.")
        return

    file_to_process = None
    temp_merged_path = None

    # If there are multiple files, merge them into a single "mega batch" file for efficiency. 
    # This avoids running the OCR and classification process multiple times for small files. 
    if len(initial_files) > 1:
        logging.info(f"Found {len(initial_files)} PDF files. Merging them into a single batch for processing.")
        temp_merged_name = f"temp_mega_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        temp_merged_path = os.path.join(INTAKE_DIR, temp_merged_name)
        file_to_process = merge_pdfs(initial_files, temp_merged_path)
    elif len(initial_files) == 1:
        logging.info("Found 1 PDF file. Processing it directly.")
        file_to_process = initial_files[0]

    if not file_to_process:
        logging.error("Failed to prepare a file for processing (merge might have failed). Halting run.")
        return
    logging.info("--- STAGE 1 COMPLETE ---")

    file_name = os.path.basename(file_to_process)
    logging.info(f"\n***************** PROCESSING BATCH: {file_name} *****************")

    # --- Safety Net Initialization ---
    all_input_pages = set()
    try:
        # Get the total page count to create a set of all pages that *should* be processed.
        with fitz.open(file_to_process) as doc:
            all_input_pages = set(range(1, doc.page_count + 1))
        logging.info(f"Initialized safety net: Found {len(all_input_pages)} total pages in the input batch.")
    except Exception as e:
        logging.critical(f"Could not open and count pages in '{file_name}'. Halting. Error: {e}")
        return
    # --- End Safety Net Initialization ---

    processed_successfully = False
    temp_split_paths: list[str] = []
    try:
        # --- STAGE 2 of 5: Performing Initial OCR on Batch ---
        logging.info("--- STAGE 2 of 5: Performing Initial OCR on Batch ---")
        full_pdf_text, page_count = perform_ocr_on_pdf(file_to_process)
        if not full_pdf_text:
            raise ValueError("Initial OCR failed to extract any text. Cannot proceed.")
        logging.info("--- STAGE 2 COMPLETE ---")

        # --- STAGE 3 of 5: Classifying Individual Pages ---
        logging.info("--- STAGE 3 of 5: Classifying Individual Pages (AI Task) ---")
        page_classifications = []
        for i in range(1, page_count + 1):
            page_text = get_text_for_page(full_pdf_text, i)
            if not page_text.strip():
                logging.warning(f"Page {i} has no text content after OCR. Assigning to 'other' category.")
                page_classifications.append({'page_num': i, 'category': 'other'})
                continue

            logging.info(f"Classifying page {i}/{page_count}...")
            category = classify_single_page(page_text)
            page_classifications.append({'page_num': i, 'category': category})
            logging.info(f"Page {i} classified as: '{category}'")

        logging.info("--- STAGE 3 COMPLETE ---")
        logging.debug(f"Full classification results: {page_classifications}")

        # --- STAGE 4 of 5: Grouping, Titling, and Ordering Documents ---
        logging.info("--- STAGE 4 of 5: Grouping, Titling, and Ordering ---")
        if not page_classifications:
            raise ValueError("No pages were classified. Cannot form document groups.")

        # This logic groups consecutive pages that share the same category. 
        document_groups: list[dict] = []
        current_group_pages = [page_classifications[0]['page_num']]
        current_category = page_classifications[0]['category']

        for i in range(1, len(page_classifications)):
            page_num, category = page_classifications[i]['page_num'], page_classifications[i]['category']
            if category == current_category:
                current_group_pages.append(page_num)
            else:
                # When the category changes, the previous group is complete. 
                document_groups.append({'category': current_category, 'pages': current_group_pages})
                # Start a new group. 
                current_group_pages = [page_num]
                current_category = category
        # Append the final group after the loop finishes. 
        document_groups.append({'category': current_category, 'pages': current_group_pages})

        logging.info(f"Identified {len(document_groups)} logical document(s) based on classification blocks.")

        # Process each logical document group with AI for titling and ordering. 
        final_documents = []
        for group in document_groups:
            pages = group['pages']
            category = group['category']

            # Consolidate the text for this group to send to the AI. 
            group_text_blob = "".join(
                PAGE_MARKER_TEMPLATE.format(page_num) + get_text_for_page(full_pdf_text, page_num)
                for page_num in pages
            )

            # AI Task 2: Generate Title 
            title = generate_title_for_group(group_text_blob, category)
            # AI Task 3: Determine Page Order 
            page_order = get_correct_page_order(group_text_blob, pages)

            final_documents.append({
                'category': category,
                'title': title,
                'page_order': page_order # This will fall back to original order if AI fails
            })
        logging.info("--- STAGE 4 COMPLETE ---")

        # --- Safety Net Verification ---
        all_processed_pages = set()
        for doc in final_documents:
            all_processed_pages.update(doc.get('page_order', []))

        lost_pages = sorted(list(all_input_pages - all_processed_pages))

        if lost_pages:
            logging.critical(f"CRITICAL: {len(lost_pages)} pages were lost during processing! Pages: {lost_pages}. Creating a '_lost_and_found' document for them.")
            
            # Ensure the category exists for the lost pages
            lost_category_name = "_lost_and_found"
            if lost_category_name not in ABSOLUTE_CATEGORIES:
                lost_path = os.path.join(PROCESSED_DIR, lost_category_name)
                os.makedirs(lost_path, exist_ok=True)
                ABSOLUTE_CATEGORIES[lost_category_name] = lost_path
                logging.info(f"Created directory for lost pages: {lost_path}")

            final_documents.append({
                'category': lost_category_name,
                'title': f"Lost_Pages_from_{os.path.splitext(file_name)[0]}",
                'page_order': lost_pages
            })
            logging.info(f"Added '_lost_and_found' document group with pages: {lost_pages}")
        else:
            logging.info("Safety net check passed: All input pages are accounted for in the final document groups.")
        # --- End Safety Net Verification ---

        # --- STAGE 5 of 5: Splitting and Creating Final Files ---
        logging.info("--- STAGE 5 of 5: Splitting and Creating Final Files ---")
        temp_split_paths = split_and_process_pdf(file_to_process, final_documents)
        logging.info("--- STAGE 5 COMPLETE ---")

        processed_successfully = True

    except Exception as e:
        # Catch-all for any unexpected errors during the main processing stages. 
        logging.critical(f"A critical, unhandled error occurred while processing '{file_name}': {e}", exc_info=True)
        processed_successfully = False # Ensure files are not archived if processing fails
    finally:
        # --- Final Cleanup ---
        logging.info("--- Starting Final Cleanup ---")
        if processed_successfully:
            logging.info(f"Batch '{file_name}' processed successfully. Archiving original files.")
            for original_file in initial_files:
                if os.path.exists(original_file):
                    if DRY_RUN:
                        logging.info(f"[DRY RUN] Would archive original file: {os.path.basename(original_file)}")
                    else:
                        try:
                            # Move the original file from INTAKE_DIR to ARCHIVE_DIR. 
                            shutil.move(original_file, os.path.join(ARCHIVE_DIR, os.path.basename(original_file)))
                            logging.info(f"Archived original file: {os.path.basename(original_file)}")
                        except Exception as e:
                            logging.error(f"Failed to archive original file '{os.path.basename(original_file)}': {e}")
        else:
            logging.warning(f"Processing for '{file_name}' was not successful. Original files will remain in '{INTAKE_DIR}' for the next run.")

        # Clean up the temporary merged file, if one was created. 
        if temp_merged_path and os.path.exists(temp_merged_path):
            try:
                os.remove(temp_merged_path)
                logging.info(f"Removed temporary merged file: {os.path.basename(temp_merged_path)}")
            except Exception as e:
                logging.error(f"Failed to remove temporary merged file: {e}")

        # Clean up all temporary split files. 
        if temp_split_paths:
            for temp_path in temp_split_paths:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                        logging.info(f"Removed temporary split file: {os.path.basename(temp_path)}")
                    except Exception as e:
                        logging.error(f"Failed to remove temporary file '{temp_path}': {e}")

    logging.info(f"***************** FINISHED PROCESSING BATCH: {file_name} *****************")
    logging.info("\n" + "="*60 + "\n============== DOCUMENT PROCESSING RUN COMPLETE ===============\n" + "="*60)



# This standard Python construct ensures that the `main()` function is called only when
# the script is executed directly (e.g., `python document_processor.py`), not when it's
# imported as a module into another script. 
if __name__ == "__main__":
    main()

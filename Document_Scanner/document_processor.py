# document_processor.py
#
# This script automates the processing, categorization, and archiving of PDF documents.
# It monitors an intake directory for new PDF files, performs Optical Character Recognition (OCR)
# on them (especially for scanned, image-only PDFs), uses a Google Gemini AI model to
# classify the documents into predefined categories and generate human-readable titles,
# and then renames and moves the processed documents (along with an OCR'd copy and a
# detailed Markdown analysis report) to their respective category folders.
#
# Key Features:
# - Automated monitoring of an intake directory.
# - Robust OCR capabilities for extracting text from various PDF types.
# - AI-powered categorization and title generation for improved organization.
# - Human-readable file naming convention based on AI analysis.
# - Generation of Markdown reports detailing OCR text and LLM interaction for auditing.
# - Support for a "dry run" mode to test functionality without altering files.
#
# Dependencies:
# - PyMuPDF (fitz): For PDF manipulation, text extraction, and rendering.
# - pytesseract: Python wrapper for Google's Tesseract OCR engine.
# - Pillow (PIL): Python Imaging Library, used for image processing with pytesseract.
# - requests: For making HTTP requests to the Google Gemini API.
# - os, shutil, fitz, json, time, requests, io, mimetypes, datetime, pytesseract, PIL: Standard Python libraries for file operations,
#   PDF manipulation, JSON handling, time utilities, date/time formatting, and image processing.
#
# Configuration:
# - API_KEY: Your Google Gemini API key, loaded from config.py.
# - DRY_RUN: Boolean flag, loaded from config.py, to enable/disable dry run mode.
# - API_URL: Endpoint for the Google Gemini Flash model.
# - INTAKE_DIR: Directory where new scanned documents are placed.
# - PROCESSED_DIR: Base directory where categorized documents will be stored.
# - CATEGORIES: A dictionary mapping document categories to their respective subdirectories.

import os
import shutil
import fitz  # PyMuPDF for PDF manipulation and OCR-related tasks
import json
import time
import requests
import io
import mimetypes
from datetime import datetime, timedelta
import pytesseract  # Python wrapper for Tesseract OCR
from PIL import Image  # Python Imaging Library for image processing
import logging # Import the logging module

# --- Environment Configuration ---
# This section handles the import of sensitive API keys and operational flags
# from a separate configuration file (config.py). This is a best practice
# for security and ease of management, preventing hardcoding of credentials.
try:
    # Attempt to import all necessary configuration variables from config.py.
    from config import API_KEY, DRY_RUN, API_URL, INTAKE_DIR, PROCESSED_DIR, CATEGORIES, LOG_FILE, LOG_LEVEL, ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS, MAX_RETRIES, RETRY_DELAY_SECONDS
except ImportError:
    # If config.py is not found or the variables are not set, print an error
    # and exit the script, as essential configuration is missing.
    print("Error: config.py not found or essential variables not set.")
    print("Please ensure config.py exists and contains API_KEY, DRY_RUN, API_URL, INTAKE_DIR, PROCESSED_DIR, CATEGORIES, LOG_FILE, LOG_LEVEL, ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS, MAX_RETRIES, RETRY_DELAY_SECONDS.")
    exit(1)

# --- Logging Setup ---
# Configure the logging system.
log_level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}
logging.basicConfig(
    level=log_level_map.get(LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE) if LOG_FILE else logging.NullHandler(),
        logging.StreamHandler() # Always output to console
    ]
)

# Dynamically construct absolute paths for categories based on PROCESSED_DIR
# The CATEGORIES dictionary in config.py now holds relative paths.
ABSOLUTE_CATEGORIES = {
    category_name: os.path.join(PROCESSED_DIR, relative_path)
    for category_name, relative_path in CATEGORIES.items()
}

# Ensure all defined category directories exist. If they don't, they will be created.
# `exist_ok=True` prevents an error if the directory already exists.
for category_path in ABSOLUTE_CATEGORIES.values():
    os.makedirs(category_path, exist_ok=True)

# Ensure ARCHIVE_DIR exists
os.makedirs(ARCHIVE_DIR, exist_ok=True)

def cleanup_archive(directory, retention_days):
    """
    Deletes files in the specified directory older than retention_days.

    Args:
        directory (str): The absolute path to the directory to clean up.
        retention_days (int): Files older than this many days will be deleted.
    """
    logging.info(f"Starting archive cleanup in {directory}. Deleting files older than {retention_days} days.")
    now = datetime.now()
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            try:
                # Get last modification time
                mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                if (now - mod_time).days > retention_days:
                    if DRY_RUN:
                        logging.info(f"[DRY RUN] Would have deleted old archive file: {file_path}")
                    else:
                        os.remove(file_path)
                        logging.info(f"Deleted old archive file: {file_path}")
            except Exception as e:
                logging.error(f"Error cleaning up archive file {file_path}: {e}")
    logging.info("Archive cleanup complete.")

# --- LLM Functions ---
def get_document_category(document_text):
    """
    Sends the extracted text of a document to the Google Gemini AI model
    to determine its category and generate a concise, human-readable title.
    It constructs a specific prompt and expects a JSON response.

    Args:
        document_text (str): The full text extracted from the document (via OCR or direct extraction).

    Returns:
        tuple: A tuple containing:
            - category (str): The classified category of the document (e.g., "invoices", "recipes").
            - title (str): A concise, human-readable title generated by the LLM.
            - reason (str): A status message indicating success or the type of error.
            - user_query (str): The exact prompt sent to the LLM.
            - raw_llm_response (str): The raw JSON response received from the LLM.
    """
    # Check if the API key is set. If not, return default values and an error message.
    if not API_KEY:
        logging.error("API_KEY is not set. Cannot use Google AI Studio.")
        return "other", "untitled", "API_KEY not set", "", ""

    # Define the system prompt for the LLM. This guides the AI's behavior and role.
    # It instructs the LLM to classify the document into one of the predefined categories
    # and to also provide a concise title (max 10 words) in JSON format.
    system_prompt = f"You are a document classification assistant for a home user's personal archive. Your task is to analyze the provided document text and classify it into one of the following categories: {', '.join(ABSOLUTE_CATEGORIES.keys())}. Focus solely on the primary subject matter of the document. Additionally, provide a concise, human-readable title (maximum 10 words) that accurately reflects the main content. Avoid combining unrelated topics in the title or category. Your response must be in JSON format with 'category' and 'title' fields."
    
    # Define the user query, which contains the document text to be analyzed.
    user_query = f"Classify and title the following document text:\n\n{document_text}"

    # Construct the payload for the API call to the Google Gemini model.
    # This includes the content (user query), system instruction (system prompt),
    # and generation configuration, specifying the expected JSON response format.
    payload = {
        "contents": [
            {"parts": [{"text": user_query}]}
        ],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "responseMimeType": "application/json", # Specify JSON response
            "responseSchema": { # Define the schema for the expected JSON output
                "type": "OBJECT",
                "properties": {
                    "category": {"type": "STRING"}, # Expected 'category' field
                    "title": {"type": "STRING"}    # Expected 'title' field
                }
            }
        },
    }

    headers = {'Content-Type': 'application/json'}
    params = {'key': API_KEY} if API_KEY else {}

    for attempt in range(MAX_RETRIES):
        try:
            # Make the POST request to the Google Gemini API.
            response = requests.post(API_URL, headers=headers, json=payload, params=params)
            # Raise an HTTPError for bad responses (4xx or 5xx).
            response.raise_for_status() 

            # Parse the JSON response from the LLM.
            result = response.json()
            raw_llm_response = json.dumps(result, indent=2) # Store raw response for debugging/logging

            # Check if the response contains valid candidates and content.
            if result and 'candidates' in result and result['candidates'][0].get('content'):
                # Extract the text part of the LLM's content, which should be a JSON string.
                response_json_str = result['candidates'][0]['content']['parts'][0]['text']
                # Parse the JSON string to get the category and title.
                response_data = json.loads(response_json_str)
                category = response_data.get('category', 'other').lower() # Get category, default to 'other'
                title = response_data.get('title', 'untitled') # Get title, default to 'untitled'

                # Validate if the returned category is one of the predefined categories.
                if category in CATEGORIES:
                    return category, title, "Success", user_query, raw_llm_response
                else:
                    # If the LLM returns an invalid category, default to 'other' and log the issue.
                    logging.warning(f"LLM returned invalid category: {category}. Defaulting to 'other'.")
                    return "other", title, f"Invalid category returned: {category}", user_query, raw_llm_response

            # If no valid response or candidates are found, log and retry if attempts remain.
            logging.warning(f"Attempt {attempt + 1}/{MAX_RETRIES}: No valid response from LLM or candidates not found.")

        # Handle various types of request exceptions for robust error reporting.
        except requests.exceptions.HTTPError as errh:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: HTTP Error: {errh}")
        except requests.exceptions.ConnectionError as errc:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Error Connecting: {errc}")
        except requests.exceptions.Timeout as errt:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Timeout Error: {errt}")
        except requests.exceptions.RequestException as err:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Request Exception: {err}")
        # Handle JSON parsing errors if the LLM response is not valid JSON.
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: JSON parsing error from LLM: {e}")
        
        # If not the last attempt, wait before retrying
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY_SECONDS)
    
    # If all attempts fail
    logging.error(f"All {MAX_RETRIES} attempts failed for get_document_category.")
    return "other", "untitled", "All LLM attempts failed.", user_query, "No valid response after retries."

def get_document_page_ranges(document_text):
    """
    Sends the extracted text of a multi-page document to the Google Gemini AI model
    to identify page ranges for individual logical documents within it.

    Args:
        document_text (str): The full text extracted from the multi-page PDF.

    Returns:
        list: A list of dictionaries, where each dictionary contains 'start_page' and 'end_page'
              indicating the page range for a logical document. Returns an empty list if no
              ranges are identified or an error occurs.
    """
    if not API_KEY:
        logging.error("API_KEY is not set. Cannot use Google AI Studio for page range detection.")
        return []

    system_prompt = "You are a document segmentation assistant. Your primary task is to analyze the provided text from a multi-page PDF and identify the precise page ranges for each *distinct and logically separate* document within it. **Crucially, avoid over-splitting; only separate documents when there is a clear and unambiguous logical break, such as a new document starting or a significant change in subject matter.** Be aware that pages belonging to the same logical document might not be contiguous (e.g., due to double-sided scanning where pages are interleaved). If a page contains content from two clearly different documents, consider it a boundary. Return a JSON array of objects, where each object has 'start_page' (1-indexed) and 'end_page' (1-indexed) fields. Ensure each identified document is self-contained. If no clear boundaries are found, assume the entire text constitutes a single document."
    user_query = f"Identify document page ranges in the following text:\n\n{document_text}"

    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "start_page": {"type": "INTEGER"},
                        "end_page": {"type": "INTEGER"}
                    },
                    "required": ["start_page", "end_page"]
                }
            }
        },
    }

    headers = {'Content-Type': 'application/json'}
    params = {'key': API_KEY} if API_KEY else {}

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, params=params)
            response.raise_for_status() 

            # Parse the JSON response from the LLM.
            result = response.json()
            raw_llm_response = json.dumps(result, indent=2) # Store raw response for debugging/logging

            # Check if the response contains valid candidates and content.
            if result and 'candidates' in result and result['candidates'][0].get('content'):
                # Extract the text part of the LLM's content, which should be a JSON string.
                response_json_str = result['candidates'][0]['content']['parts'][0]['text']
                # Parse the JSON string to get the page ranges.
                page_ranges = json.loads(response_json_str)
                
                # Basic validation for the structure of page_ranges
                if isinstance(page_ranges, list) and all(isinstance(pr, dict) and 'start_page' in pr and 'end_page' in pr for pr in page_ranges):
                    return page_ranges
                else:
                    logging.warning(f"Attempt {attempt + 1}/{MAX_RETRIES}: LLM returned invalid page ranges format: {response_json_str}. Returning empty list.")
                    # Do not break here, allow retry if format is consistently bad
            
            # If no valid response or candidates are found, log and retry if attempts remain.
            logging.warning(f"Attempt {attempt + 1}/{MAX_RETRIES}: No valid response from LLM or candidates not found for page ranges.")

        # Handle various types of request exceptions for robust error reporting.
        except requests.exceptions.HTTPError as errh:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: HTTP Error: {errh}")
        except requests.exceptions.ConnectionError as errc:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Error Connecting: {errc}")
        except requests.exceptions.Timeout as errt:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Timeout Error: {errt}")
        except requests.exceptions.RequestException as err:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Request Exception: {err}")
        # Handle JSON parsing errors if the LLM response is not valid JSON.
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: JSON parsing error from LLM: {e}")
        
        # If not the last attempt, wait before retrying
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY_SECONDS)
    
    # If all attempts fail
    logging.error(f"All {MAX_RETRIES} attempts failed for get_document_page_ranges.")
    return []

def split_pdf_by_page_ranges(original_pdf_path, page_ranges):
    """
    Splits a multi-page PDF into individual PDF files based on a list of page ranges.
    Args:
        original_pdf_path (str): The path to the original multi-page PDF file.
        page_ranges (list): A list of dictionaries, where each dictionary contains
                            'start_page' and 'end_page' (1-indexed) for a logical document.

    Returns:
        list: A list of paths to the newly created temporary individual PDF files.
    """
    split_pdf_paths = []
    try:
        original_doc = fitz.open(original_pdf_path)
        for i, page_range in enumerate(page_ranges):
            start_page = page_range['start_page'] - 1  # Convert to 0-indexed
            end_page = page_range['end_page']  # end_page is exclusive in PyMuPDF slice
            # Create a new PDF for the current document
            new_doc = fitz.open()
            new_doc.insert_pdf(original_doc, from_page=start_page, to_page=end_page)
            # Create a temporary file path for the split PDF
            temp_pdf_path = os.path.join(os.path.dirname(original_pdf_path), f"temp_split_doc_{os.path.basename(original_pdf_path)}_{i}.pdf")
            new_doc.save(temp_pdf_path)
            new_doc.close()
            split_pdf_paths.append(temp_pdf_path)
        original_doc.close()
    except Exception as e:
        logging.error(f"Error splitting PDF {original_pdf_path}: {e}")
    return split_pdf_paths

def merge_pdfs(pdf_paths, output_path):
    """
    Merges multiple PDF files into a single PDF file.

    Args:
        pdf_paths (list): A list of absolute paths to the PDF files to merge.
        output_path (str): The absolute path where the merged PDF will be saved.

    Returns:
        str: The path to the merged PDF file if successful, None otherwise.
    """
    try:
        merged_doc = fitz.open() # Create a new, empty PDF document
        for pdf_path in pdf_paths:
            doc = fitz.open(pdf_path) # Open each PDF
            merged_doc.insert_pdf(doc) # Insert its pages into the merged document
            doc.close() # Close the individual PDF
        merged_doc.save(output_path) # Save the merged document
        merged_doc.close() # Close the merged document
        logging.info(f"Successfully merged {len(pdf_paths)} PDFs into {output_path}")
        return output_path
    except Exception as e:
        logging.error(f"Error merging PDFs {pdf_paths}: {e}")
        return None

def group_front_back_scans(directory):
    """
    Groups front and back PDF scans based on a naming convention.
    Expected convention: 'document_name_front.pdf' and 'document_name_back.pdf'.

    Args:
        directory (str): The absolute path to the directory to scan for PDF files.

    Returns:
        list: A list of grouped documents. Each item is either a single file path
              (for documents without a front/back pair) or a tuple of
              (front_file_path, back_file_path) for paired documents.
    """
    files = [f for f in os.listdir(directory) if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(directory, f))]
    
    grouped_documents = []
    processed_files = set() # To keep track of files that have been grouped to avoid reprocessing

    for file_name in files:
        if file_name in processed_files:
            continue # Skip files that have already been grouped

        # Attempt to find a base name by removing common suffixes
        base_name = file_name.replace("_front.pdf", "").replace("_back.pdf", "")

        if "_front.pdf" in file_name:
            front_path = os.path.join(directory, file_name)
            back_name = file_name.replace("_front.pdf", "_back.pdf")
            back_path = os.path.join(directory, back_name)

            # Check if a corresponding back scan exists and hasn't been processed yet
            if back_name in files and back_name not in processed_files:
                grouped_documents.append((front_path, back_path))
                processed_files.add(file_name)
                processed_files.add(back_name) # Mark both front and back as processed
            else:
                # If no matching back scan, treat the front scan as a standalone document
                grouped_documents.append(front_path)
                processed_files.add(file_name)
        elif "_back.pdf" in file_name:
            # If it's a back scan and hasn't been processed (meaning no corresponding front was found first)
            if file_name not in processed_files:
                grouped_documents.append(os.path.join(directory, file_name))
                processed_files.add(file_name)
        else:
            # If it's a regular PDF (not a front/back scan)
            grouped_documents.append(os.path.join(directory, file_name))
            processed_files.add(file_name)
            
    return grouped_documents

# --- OCR and Processing Functions ---
def perform_ocr_on_pdf(file_path):
    """
    Performs OCR (Optical Character Recognition) on a PDF document to extract its text.
    If the PDF already contains extractable text, it uses that. Otherwise, it renders
    each page as an image and uses Tesseract OCR to extract text.
    It also creates a new PDF document with the extracted text embedded as a text layer,
    making the document searchable.

    Args:
        file_path (str): The absolute path to the PDF file.

    Returns:
        tuple: A tuple containing:
            - extracted_text (str): The combined text extracted from all pages of the PDF.
            - new_doc (fitz.Document): A new PyMuPDF document object with the text layer added.
                                       Returns None if an error occurs.
    """
    try:
        doc = fitz.open(file_path) # Open the PDF document using PyMuPDF
        extracted_text = ""        # Initialize an empty string to store all extracted text
        new_doc = fitz.open()      # Create a new, empty PDF document for the OCR'd version

        # Iterate through each page of the original PDF
        for page in doc:
            # Attempt to get text directly from the page. This works for PDFs that
            # already have an embedded text layer (e.g., digitally created PDFs).
            page_text = page.get_text()

            # If no text is found directly (or only whitespace), it's likely a scanned image PDF.
            if not page_text.strip():
                # Render the page to a high-resolution image for better OCR accuracy.
                # fitz.Matrix(2, 2) scales the image by 2x in both dimensions.
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                
                # Convert the PyMuPDF pixmap to a PIL Image object.
                # .convert("RGB") ensures the image is in RGB format, which Tesseract often prefers.
                img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                
                # Perform OCR on the image using pytesseract.
                ocr_text = pytesseract.image_to_string(img)
                extracted_text += ocr_text # Add the OCR'd text to the total extracted text
            else:
                # If text was found directly, use that text.
                extracted_text += page_text

            # Create a new page in the new_doc with the same dimensions as the original page.
            new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)

            # Copy the visual content (images, drawings) from the original page to the new page.
            # This ensures the visual appearance of the document is preserved.
            pix = page.get_pixmap()
            img_data = io.BytesIO(pix.tobytes("png"))
            new_page.insert_image(new_page.rect, stream=img_data)

            # Insert the extracted text (either direct or OCR'd) as an invisible text layer
            # onto the new page. This makes the PDF searchable.
            # page.rect.tl gives the top-left corner of the page, where text insertion begins.
            new_page.insert_text(page.rect.tl, page_text if page_text.strip() else ocr_text)
            
        return extracted_text, new_doc # Return the combined text and the new searchable PDF document
    except Exception as e:
        logging.error(f"Error performing OCR on {file_path}: {e}")
        return "", None # Return empty text and None for the document if an error occurs

def process_document(file_path):
    """
    Analyzes a single document: performs OCR, extracts text, categorizes it
    and generates a title using an AI model, renames the files, and moves them
    to the appropriate category folder. It also generates a Markdown report.

    Args:
        file_path (str): The absolute path to the document file to be processed.
    """
    file_name = os.path.basename(file_path) # Get just the filename from the full path
    logging.info(f"Processing file: {file_name}")

    file_extension = os.path.splitext(file_name)[1].lower() # Get the file extension

    # Skip processing if the file is not a PDF, as the script is designed for PDFs.
    if file_extension != ".pdf":
        logging.info(f"Skipping {file_name}. Only PDF files are supported.")
        return

    # 1. Perform OCR and extract text from the document.
    # document_text will contain the combined text, ocr_doc will be the new searchable PDF.
    document_text, ocr_doc = perform_ocr_on_pdf(file_path)

    # Initialize LLM interaction details
    # These variables will store the prompt sent to the LLM and its raw response,
    # which are crucial for the Markdown report to show the LLM's thought process.
    llm_user_query = ""
    llm_raw_response = ""
    reason = "" # Initialize reason for consistent Markdown output, will be updated by LLM function

    # Check if text was successfully extracted from the document.
    if not document_text:
        logging.warning(f"Could not extract text from {file_name}.")
        category = "other"   # Default category if no text for analysis
        title = "untitled"   # Default title if no text for analysis
        reason = "No text extracted for analysis." # Specific reason for Markdown report
    else:
        # 2. Analyze the extracted text with the AI model to get category and title.
        # The get_document_category function now returns 5 values:
        # category, title, reason (status), the user query sent to LLM, and the raw LLM response.
        category, title, reason, llm_user_query, llm_raw_response = get_document_category(document_text)
        # Log the AI's categorization and generated title for user feedback.
        logging.info(f"AI categorized '{file_name}' as: {category} with title: '{title}' ({reason})")

    # Sanitize the LLM-generated title to ensure it's a valid and safe filename.
    # It allows alphanumeric characters, spaces, hyphens, underscores, and periods.
    # Then, it replaces spaces with underscores for better file system compatibility.
    sanitized_title = "".join(c for c in title if c.isalnum() or c in (' ', '.', '-', '_', '(', ')')).rstrip()
    sanitized_title = sanitized_title.replace(' ', '_') # Replace spaces with underscores

    # 3. Construct new filenames and paths for the processed PDF, OCR'd PDF, and Markdown report.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") # Generate a timestamp for unique filenames

    # New filename for the original PDF (after moving) and the OCR'd copy.
    # Format: category_sanitizedtitle_timestamp.pdf (or _ocr.pdf)
    new_name = f"{category}_{sanitized_title}_{timestamp}.pdf"
    new_ocr_name = f"{category}_{sanitized_title}_{timestamp}_ocr.pdf"
    markdown_name = f"{category}_{sanitized_title}_{timestamp}.md" # Filename for the Markdown report

    # Determine the destination directory based on the classified category.
    # Uses .get() with a default to "other" if the category is not found in ABSOLUTE_CATEGORIES.
    destination_dir = ABSOLUTE_CATEGORIES.get(category, ABSOLUTE_CATEGORIES["other"])

    # Construct the full absolute paths for the destination files.
    destination_path = os.path.join(destination_dir, new_name)
    destination_ocr_path = os.path.join(destination_dir, new_ocr_name)
    markdown_path = os.path.join(destination_dir, markdown_name)

    try:
        # Move the original file to its categorized destination.
        # This operation is skipped if DRY_RUN is True.
        if DRY_RUN:
            logging.info(f"[DRY RUN] Would have moved original file to: {destination_path}")
        else:
            shutil.move(file_path, destination_path)
            logging.info(f"Moved original file to: {destination_path}")

        # Save the OCR'd copy of the PDF.
        # This operation is skipped if DRY_RUN is True.
        if ocr_doc:
            if DRY_RUN:
                logging.info(f"[DRY RUN] Would have saved OCR copy to: {destination_ocr_path}")
            else:
                ocr_doc.save(destination_ocr_path, garbage=4, deflate=True)
                ocr_doc.close() # Close the PyMuPDF document after saving to release resources
                logging.info(f"Saved OCR copy to: {destination_ocr_path}") # This log is now correctly conditional

        # Save the Markdown text file containing analysis details.
        # This operation is skipped if DRY_RUN is True.
        markdown_content = f"""# Document Analysis Report

## Original File: {file_name}
## Category: {category}
## Title: {title}

---

## Extracted Text (OCR)

```
{document_text}
```

---

## LLM Interaction Details

### Prompt to LLM
```json
{llm_user_query}
```

### Raw LLM Response
```json
{llm_raw_response}
```

### LLM Analysis Summary
- **Category:** {category}
- **Title:** {title}
- **Reason/Status:** {reason}
"""
        if DRY_RUN:
            logging.info(f"[DRY RUN] Would have saved Markdown report to: {markdown_path}")
        else:
            # Open the Markdown file in write mode with UTF-8 encoding.
            with open(markdown_path, "w", encoding="utf-8") as md_file:
                md_file.write(markdown_content) # Write the generated Markdown content
            logging.info(f"Saved Markdown report to: {markdown_path}")

    except Exception as e:
        logging.error(f"Error moving or saving file: {e}")

# --- Main Logic ---
def main():
    """
    Main function to scan the intake directory for new documents and process them.
    It iterates through all files in the INTAKE_DIR, performs document separation
    if a multi-document PDF is detected, and then processes each individual document.
    """
    logging.info(f"Starting document processing scan of {INTAKE_DIR}...")
    cleanup_archive(ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS) # Call cleanup at the start

    # Get a list of all PDF files in the intake directory before processing.
    # This initial list helps in identifying which files were present at the start
    # of the processing cycle, so they can be archived later if successfully handled.
    original_intake_pdfs = [
        os.path.join(INTAKE_DIR, f)
        for f in os.listdir(INTAKE_DIR)
        if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(INTAKE_DIR, f))
    ]
    
    # Use a set to keep track of files that have been successfully processed and are
    # candidates for archiving. This is important because a single original PDF
    # might be split into multiple logical documents, and we only want to archive
    # the original once all its parts have been processed.
    files_to_archive = set()

    grouped_documents = group_front_back_scans(INTAKE_DIR)

    for doc_group in grouped_documents:
        file_to_process = None
        temp_merged_path = None
        original_files_for_archive = [] # List to hold original paths for archiving

        if isinstance(doc_group, tuple):
            # It's a front/back pair, merge them
            front_path, back_path = doc_group
            logging.info(f"Merging front and back scans: {os.path.basename(front_path)} and {os.path.basename(back_path)}")
            
            # Create a temporary path for the merged PDF
            temp_merged_name = f"merged_{os.path.basename(front_path).replace('_front.pdf', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            temp_merged_path = os.path.join(INTAKE_DIR, temp_merged_name)
            
            file_to_process = merge_pdfs([front_path, back_path], temp_merged_path)
            
            if file_to_process:
                original_files_for_archive.extend([front_path, back_path]) # Mark originals for archiving
        else:
            # It's a single document (could be a standalone or a batch PDF)
            file_to_process = doc_group
            original_files_for_archive.append(doc_group) # Mark original for archiving

        if file_to_process:
            file_name = os.path.basename(file_to_process)
            if file_to_process.lower().endswith(".pdf"):
                logging.info(f"Processing PDF: {file_name}")
                full_pdf_text, _ = perform_ocr_on_pdf(file_to_process)

                if full_pdf_text:
                    page_ranges = get_document_page_ranges(full_pdf_text)
                    if page_ranges:
                        logging.info(f"Detected {len(page_ranges)} logical documents in {file_name}.")
                        split_docs_paths = split_pdf_by_page_ranges(file_to_process, page_ranges)
                        
                        # Process each split document
                        for doc_path in split_docs_paths:
                            process_document(doc_path)
                            # The temporary split PDF file is moved by process_document, so no explicit removal is needed here.
                        
                        # If the file_to_process was a temporary merged file, it's now done.
                        # If it was an original batch file, it's now done.
                        # Mark the original intake files for archiving.
                        for original_path in original_files_for_archive:
                            files_to_archive.add(original_path)

                    else:
                        logging.info(f"Could not determine page ranges for {file_name}. Processing as a single document.")
                        process_document(file_to_process) # This moves the single doc to its category
                        for original_path in original_files_for_archive:
                            files_to_archive.add(original_path)
                else:
                    logging.warning(f"Could not extract text from {file_name}. Skipping page range detection and processing as single document.")
                    process_document(file_to_process) # This moves the single doc to its category
                    for original_path in original_files_for_archive:
                        files_to_archive.add(original_path)
            else:
                logging.info(f"Skipping {file_name}. Only PDF files are supported for advanced processing.")
            
            # Clean up temporary merged file if it was created
            if temp_merged_path and os.path.exists(temp_merged_path):
                try:
                    os.remove(temp_merged_path)
                    logging.info(f"Removed temporary merged file: {os.path.basename(temp_merged_path)}")
                except Exception as e:
                    logging.error(f"Error removing temporary merged file {temp_merged_path}: {e}")

    # After processing all grouped documents, move the original intake files to archive
    logging.debug(f"DRY_RUN status before archiving loop: {DRY_RUN}") # Debug log to check DRY_RUN value
    for original_path in files_to_archive:
        if os.path.exists(original_path): # Check if the file still exists in INTAKE_DIR
            if DRY_RUN:
                logging.info(f"[DRY RUN] Would have archived original intake file: {os.path.basename(original_path)}")
            else:
                try:
                    shutil.move(original_path, os.path.join(ARCHIVE_DIR, os.path.basename(original_path)))
                    logging.info(f"Archived original intake file: {os.path.basename(original_path)}")
                except Exception as e:
                    logging.error(f"Error archiving original intake file {original_path}: {e}")

    logging.info("Scan complete.") # Indicate that the scan has finished

# Standard boilerplate to ensure main() is called when the script is executed directly.
if __name__ == "__main__":
    main()

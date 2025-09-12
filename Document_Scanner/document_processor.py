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
from datetime import datetime
import pytesseract  # Python wrapper for Tesseract OCR
from PIL import Image  # Python Imaging Library for image processing

# --- Environment Configuration ---
# This section handles the import of sensitive API keys and operational flags
# from a separate configuration file (config.py). This is a best practice
# for security and ease of management, preventing hardcoding of credentials.
try:
    # Attempt to import API_KEY and DRY_RUN from a separate config.py file.
    # The config.py file should contain:
    # API_KEY = "YOUR_GOOGLE_GEMINI_API_KEY"
    # DRY_RUN = True  # or False
    from config import API_KEY, DRY_RUN
except ImportError:
    # If config.py is not found or the variables are not set, print an error
    # and exit the script, as essential configuration is missing.
    print("Error: config.py not found or API_KEY/DRY_RUN not set.")
    print("Please create a config.py file with your API_KEY and DRY_RUN = True/False.")
    exit(1)

# API URL for Google's Gemini Flash model. This is the endpoint to which
# document text will be sent for classification and title generation.
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# Directories for document processing. These paths should be accessible by the script.
# INTAKE_DIR: Where new, unprocessed documents are initially placed.
INTAKE_DIR = "/mnt/scans_intake"
# PROCESSED_DIR: The base directory where all processed and categorized documents
# will be moved. Subdirectories for each category will be created here.
PROCESSED_DIR = "/mnt/scans_processed"

# Define the document categories and their corresponding paths within PROCESSED_DIR.
# The script will attempt to classify documents into one of these categories.
# If a document cannot be classified, it defaults to the "other" category.
CATEGORIES = {
    "invoices": os.path.join(PROCESSED_DIR, "invoices"),
    "receipts": os.path.join(PROCESSED_DIR, "receipts"),
    "reports": os.path.join(PROCESSED_DIR, "reports"),
    "letters": os.path.join(PROCESSED_DIR, "letters"),
    "legal": os.path.join(PROCESSED_DIR, "legal"),
    "medical": os.path.join(PROCESSED_DIR, "medical"),
    "recipes": os.path.join(PROCESSED_DIR, "recipes"),
    "pictures": os.path.join(PROCESSED_DIR, "pictures"),
    "instruction_manuals": os.path.join(PROCESSED_DIR, "instruction_manuals"),
    "other": os.path.join(PROCESSED_DIR, "other") # Default category for unclassifiable documents
}

# Ensure all defined category directories exist. If they don't, they will be created.
# `exist_ok=True` prevents an error if the directory already exists.
for category_path in CATEGORIES.values():
    os.makedirs(category_path, exist_ok=True)

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
        print("API_KEY is not set. Cannot use Google AI Studio.")
        return "other", "untitled", "API_KEY not set", "", ""

    # Define the system prompt for the LLM. This guides the AI's behavior and role.
    # It instructs the LLM to classify the document into one of the predefined categories
    # and to also provide a concise title (max 10 words) in JSON format.
    system_prompt = f"You are a document classification assistant for a home user's personal archive. Your task is to analyze the text of a document and classify it into one of the following categories: {', '.join(CATEGORIES.keys())}. Additionally, provide a concise, human-readable title for the document (max 10 words). Your response should be in JSON format with 'category' and 'title' fields."
    
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
                # If the LLM returns an invalid category, default to 'other' and report the issue.
                return "other", title, f"Invalid category returned: {category}", user_query, raw_llm_response

        # If no valid response or candidates are found, return default values.
        return "other", "untitled", "No valid response from LLM.", user_query, raw_llm_response

    # Handle various types of request exceptions for robust error reporting.
    except requests.exceptions.HTTPError as errh:
        return "other", "untitled", f"HTTP Error: {errh}", user_query, str(errh)
    except requests.exceptions.ConnectionError as errc:
        return "other", "untitled", f"Error Connecting: {errc}", user_query, str(errc)
    except requests.exceptions.Timeout as errt:
        return "other", "untitled", f"Timeout Error: {errt}", user_query, str(errt)
    except requests.exceptions.RequestException as err:
        return "other", "untitled", f"Request Exception: {err}", user_query, str(err)
    # Handle JSON parsing errors if the LLM response is not valid JSON.
    except (json.JSONDecodeError, IndexError, KeyError) as e:
        return "other", "untitled", f"JSON parsing error: {e}", user_query, "Invalid JSON response"

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
        print("API_KEY is not set. Cannot use Google AI Studio for page range detection.")
        return []

    system_prompt = "You are a document segmentation assistant. Analyze the provided text from a multi-page PDF and identify the page ranges for each distinct logical document within it. Return a JSON array of objects, where each object has 'start_page' (1-indexed) and 'end_page' (1-indexed) fields. If there is only one document, return a single object covering all pages. If no clear boundaries are found, assume the entire text is one document."
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
    try:
        response = requests.post(API_URL, headers=headers, json=payload, params=params)
        response.raise_for_status()
        result = response.json()

        if result and 'candidates' in result and result['candidates'][0].get('content'):
            response_json_str = result['candidates'][0]['content']['parts'][0]['text']
            page_ranges = json.loads(response_json_str)
            # Basic validation of the returned structure
            if isinstance(page_ranges, list) and all(isinstance(r, dict) and 'start_page' in r and 'end_page' in r for r in page_ranges):
                return page_ranges
            else:
                print(f"LLM returned invalid page range format: {response_json_str}")
                return []
        return []

    except requests.exceptions.RequestException as e:
        print(f"Error during LLM page range detection request: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"JSON decoding error from LLM page range detection: {e}")
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
        print(f"Error splitting PDF {original_pdf_path}: {e}")
    return split_pdf_paths

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
            new_page.insert_text(page.rect.tl, extracted_text)
            
        return extracted_text, new_doc # Return the combined text and the new searchable PDF document
    except Exception as e:
        # Catch any exceptions during OCR or PDF processing and print an error message.
        print(f"Error performing OCR on {file_path}: {e}")
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
    print(f"Processing file: {file_name}")

    file_extension = os.path.splitext(file_name)[1].lower() # Get the file extension

    # Skip processing if the file is not a PDF, as the script is designed for PDFs.
    if file_extension != ".pdf":
        print(f"Skipping {file_name}. Only PDF files are supported.")
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
        print(f"Could not extract text from {file_name}.")
        category = "other"   # Default category if no text for analysis
        title = "untitled"   # Default title if no text for analysis
        reason = "No text extracted for analysis." # Specific reason for Markdown report
    else:
        # 2. Analyze the extracted text with the AI model to get category and title.
        # The get_document_category function now returns 5 values:
        # category, title, reason (status), the user query sent to LLM, and the raw LLM response.
        category, title, reason, llm_user_query, llm_raw_response = get_document_category(document_text)
        # Print the AI's categorization and generated title for user feedback.
        print(f"AI categorized '{file_name}' as: {category} with title: '{title}' ({reason})")

    # Sanitize the LLM-generated title to ensure it's a valid and safe filename.
    # It removes characters that are not alphanumeric, spaces, periods, or underscores.
    # Then, it replaces spaces with underscores for better file system compatibility.
    sanitized_title = "".join(c for c in title if c.isalnum() or c in (' ', '.', '_')).rstrip()
    sanitized_title = sanitized_title.replace(' ', '_') # Replace spaces with underscores

    # 3. Construct new filenames and paths for the processed PDF, OCR'd PDF, and Markdown report.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") # Generate a timestamp for unique filenames

    # New filename for the original PDF (after moving) and the OCR'd copy.
    # Format: category_sanitizedtitle_timestamp.pdf (or _ocr.pdf)
    new_name = f"{category}_{sanitized_title}_{timestamp}.pdf"
    new_ocr_name = f"{category}_{sanitized_title}_{timestamp}_ocr.pdf"
    markdown_name = f"{category}_{sanitized_title}_{timestamp}.md" # Filename for the Markdown report

    # Determine the destination directory based on the classified category.
    # Uses .get() with a default to "other" if the category is not found in CATEGORIES.
    destination_dir = CATEGORIES.get(category, CATEGORIES["other"])

    # Construct the full absolute paths for the destination files.
    destination_path = os.path.join(destination_dir, new_name)
    destination_ocr_path = os.path.join(destination_dir, new_ocr_name)
    markdown_path = os.path.join(destination_dir, markdown_name)

    try:
        # Move the original file to its categorized destination.
        # This operation is skipped if DRY_RUN is True.
        if DRY_RUN:
            print(f"[DRY RUN] Would have moved original file to: {destination_path}")
        else:
            shutil.move(file_path, destination_path)
            print(f"Moved original file to: {destination_path}")

        # Save the OCR'd copy of the PDF.
        # This operation is skipped if DRY_RUN is True.
        if ocr_doc:
            if DRY_RUN:
                print(f"[DRY RUN] Would have saved OCR copy to: {destination_ocr_path}")
            else:
                ocr_doc.save(destination_ocr_path, garbage=4, deflate=True)
                ocr_doc.close() # Close the PyMuPDF document after saving to release resources
                print(f"Saved OCR copy to: {destination_ocr_path}") # This print is now correctly conditional

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
            print(f"[DRY RUN] Would have saved Markdown report to: {markdown_path}")
        else:
            # Open the Markdown file in write mode with UTF-8 encoding.
            with open(markdown_path, "w", encoding="utf-8") as md_file:
                md_file.write(markdown_content) # Write the generated Markdown content
            print(f"Saved Markdown report to: {markdown_path}")

    except Exception as e:
        # Catch any errors during file moving or saving and report them.
        print(f"Error moving or saving file: {e}")

# --- Main Logic ---
def main():
    """
    Main function to scan the intake directory for new documents and process them.
    It iterates through all files in the INTAKE_DIR, performs document separation
    if a multi-document PDF is detected, and then processes each individual document.
    """
    print(f"Starting document processing scan of {INTAKE_DIR}...")

    # Iterate through all files in the intake directory.
    for file_name in os.listdir(INTAKE_DIR):
        file_path = os.path.join(INTAKE_DIR, file_name) # Construct the full path to the file
        # Check if the current item is a file (and not a subdirectory).
        if os.path.isfile(file_path):
            if file_path.lower().endswith(".pdf"):
                print(f"Processing PDF: {file_name}")
                # Perform OCR on the entire PDF to get text for page range detection
                full_pdf_text, _ = perform_ocr_on_pdf(file_path)

                if full_pdf_text:
                    page_ranges = get_document_page_ranges(full_pdf_text)
                    if page_ranges:
                        print(f"Detected {len(page_ranges)} logical documents in {file_name}.")
                        split_docs_paths = split_pdf_by_page_ranges(file_path, page_ranges)
                        for doc_path in split_docs_paths:
                            process_document(doc_path)
                            # Clean up temporary split PDF file
                            try:
                                os.remove(doc_path)
                                print(f"Removed temporary file: {doc_path}")
                            except Exception as e:
                                print(f"Error removing temporary file {doc_path}: {e}")
                    else:
                        print(f"Could not determine page ranges for {file_name}. Processing as a single document.")
                        process_document(file_path)
                else:
                    print(f"Could not extract text from {file_name}. Skipping page range detection and processing as single document.")
                    process_document(file_path)
            else:
                print(f"Skipping {file_name}. Only PDF files are supported for advanced processing.")
                # For non-PDFs, we can still process them if process_document handles them,
                # but for now, we'll just skip as per the original script's intent.
                # process_document(file_path) # Uncomment if you want to process other file types

    print("Scan complete.") # Indicate that the scan has finished

# Standard boilerplate to ensure main() is called when the script is executed directly.
if __name__ == "__main__":
    main()
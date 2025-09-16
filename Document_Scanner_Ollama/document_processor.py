# document_processor.py (Ollama Version with Full Context from Config)
#
# This script automates the processing of PDF documents from an intake directory.
# It performs the following key steps:
# 1. Merges multiple input PDFs into a single file for batch processing.
# 2. Uses Optical Character Recognition (OCR) to extract text from the PDFs.
# 3. Leverages a local Ollama LLM to analyze the extracted text, group pages into
#    logical documents, and determine the correct page order within each document.
# 4. Splits the merged PDF into individual, correctly ordered documents.
# 5. Saves the processed documents into categorized folders with standardized filenames.
# 6. Generates a text-searchable OCR copy and a Markdown summary for each document.
# 7. Archives the original files and performs regular cleanup of the archive.
#
# The script is designed to be robust, with features like retry logic for AI calls,
# flexible parsing of AI responses, and detailed logging.

import os
import shutil
import fitz  # PyMuPDF for PDF manipulation
import json
import time
import io
import re
from datetime import datetime, timedelta
import pytesseract  # For OCR
from PIL import Image
import logging
import ollama  # Ollama's Python client
from prompts import GROUPING_PROMPT_TEMPLATE, ORDERING_PROMPT

# --- Environment and Configuration ---
# This section loads all necessary settings from the 'config.py' file.
# It's wrapped in a try-except block to handle cases where the config is missing
# or key variables are not defined, preventing the script from running with errors.
try:
    # Import all configuration variables. A key update is the inclusion of
    # OLLAMA_CONTEXT_WINDOW, which allows the script to specify the context size for the LLM.
    from config import (
        DRY_RUN, OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_CONTEXT_WINDOW,
        INTAKE_DIR, PROCESSED_DIR, CATEGORIES, LOG_FILE, LOG_LEVEL,
        ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS, MAX_RETRIES, RETRY_DELAY_SECONDS
    )
except ImportError:
    print("Error: config.py not found or essential variables not set.")
    exit(1)

# Initialize the Ollama client. This is also in a try-except block to catch
# critical errors if the Ollama service is not running or accessible.
try:
    ollama_client = ollama.Client(host=OLLAMA_HOST)
except Exception as e:
    print(f"CRITICAL: Failed to create Ollama client for host {OLLAMA_HOST}. Is Ollama running? Error: {e}")
    exit(1)

# --- Constants, Logging, and Path Setup ---
# A consistent marker to separate pages when they are concatenated into a single text block.
PAGE_MARKER_TEMPLATE = "\n\n--- Page {} ---\n\n"

# Configure the logging system. It can log to a file and/or the console,
# with the level determined by the LOG_LEVEL setting in config.py.
log_level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}
logging.basicConfig(
    level=log_level_map.get(LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE) if LOG_FILE else logging.NullHandler(),
        logging.StreamHandler()
    ]
)

# Create absolute paths for all destination category directories and the archive directory.
# This ensures the script can reliably move files to their final locations.
ABSOLUTE_CATEGORIES = {category_name: os.path.join(PROCESSED_DIR, relative_path) for category_name, relative_path in CATEGORIES.items()}
for category_path in ABSOLUTE_CATEGORIES.values():
    os.makedirs(category_path, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

def cleanup_archive(directory, retention_days):
    """
    Removes files from the archive directory that are older than the specified retention period.
    This helps manage disk space by deleting outdated original files.
    """
    logging.info(f"Starting archive cleanup in {directory}. Deleting files older than {retention_days} days.")
    now = datetime.now()
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            try:
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


# --- LLM Functions (with Full Context Enabled) ---
def analyze_and_group_document(document_text):
    """
    AI CALL #1: Sends the full text of all documents to the Ollama model and asks it
    to group pages into logical documents based on content.
    
    This function includes robust logic to parse potentially inconsistent JSON output
    from the LLM, making the system more reliable.
    """
    categories_list = ', '.join(CATEGORIES.keys())
    system_prompt = GROUPING_PROMPT_TEMPLATE.format(categories_list=categories_list)
    user_query = f"Analyze and group the documents in the following text:\n\n{document_text}"
    messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_query}]
    
    # Set the context window size for the Ollama model. This is crucial for ensuring
    # the model can "see" all the text from a large batch of documents at once.
    options = {'num_ctx': OLLAMA_CONTEXT_WINDOW}

    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Sending grouping request to Ollama model '{OLLAMA_MODEL}' (Attempt {attempt + 1})...")
            response = ollama_client.chat(model=OLLAMA_MODEL, messages=messages, format='json', options=options)
            response_content = response['message']['content']
            logging.debug(f"Raw Ollama grouping response content:\n---\n{response_content}\n---")
            
            parsed_json = json.loads(response_content)

            # --- NEW, MORE ROBUST PARSING LOGIC ---
            # This block handles various JSON formats the AI might return.
            if isinstance(parsed_json, list):
                # Case 1: The AI returned the correct format (a list of document objects).
                logging.debug("AI returned a valid list of documents.")
                return parsed_json
            elif isinstance(parsed_json, dict):
                # Case 2: The AI wrapped the list in a dictionary (e.g., {"documents": [...]}).
                for key, value in parsed_json.items():
                    if isinstance(value, list):
                        logging.debug(f"AI returned a dictionary; extracting the list from key '{key}'.")
                        return value
                # Case 3: The AI returned a single document object, not in a list.
                logging.debug("AI returned a single dictionary with no list inside; wrapping it in a list.")
                return [parsed_json]

            logging.warning(f"AI returned an unknown JSON structure of type {type(parsed_json)}.")
            return []

        except (ollama.ResponseError, json.JSONDecodeError, KeyError) as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Document grouping analysis failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
        except Exception as e:
            logging.critical(f"An unexpected error occurred during Ollama grouping call: {e}")
            break
    return []

def get_correct_page_order(document_group_text):
    """
    AI CALL #2: For a single logical document (a group of pages), this function asks
    the Ollama model to determine the correct reading order of the pages.
    """
    system_prompt = ORDERING_PROMPT
    user_query = f"Determine the correct page order for the following document text:\n\n{document_group_text}"
    messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_query}]
    
    # Again, use the full context window to ensure the model sees all pages of the subgroup.
    options = {'num_ctx': OLLAMA_CONTEXT_WINDOW}

    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Sending ordering request to Ollama model '{OLLAMA_MODEL}' (Attempt {attempt + 1})...")
            response = ollama_client.chat(model=OLLAMA_MODEL, messages=messages, format='json', options=options)
            response_content = response['message']['content']
            logging.debug(f"Raw Ollama ordering response content:\n---\n{response_content}\n---")
            return json.loads(response_content).get("page_order")
        except (ollama.ResponseError, json.JSONDecodeError, KeyError) as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Page ordering analysis failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
        except Exception as e:
            logging.critical(f"An unexpected error occurred during Ollama ordering call: {e}")
            break
    return None

# --- Helper and PDF Processing Functions ---
def get_text_for_page(full_text, page_number):
    """
    Extracts the text of a specific page from the concatenated full text string,
    using the page markers that were inserted during OCR.
    """
    start_marker = PAGE_MARKER_TEMPLATE.format(page_number).strip()
    pattern = re.compile(re.escape(start_marker) + r'\n(.*?)(?=\n--- Page|\Z)', re.DOTALL)
    match = pattern.search(full_text)
    return match.group(1).strip() if match else ""

def merge_pdfs(pdf_paths, output_path):
    """
    Combines multiple PDF files into a single PDF file. This is done to create a
    single "batch" document that can be processed by the AI in one go.
    """
    try:
        merged_doc = fitz.open()
        for pdf_path in pdf_paths:
            with fitz.open(pdf_path) as doc:
                merged_doc.insert_pdf(doc)
        merged_doc.save(output_path)
        merged_doc.close()
        logging.info(f"Successfully merged {len(pdf_paths)} PDFs into temporary file: {os.path.basename(output_path)}")
        return output_path
    except Exception as e:
        logging.error(f"Error merging PDFs: {e}")
        return None
        
def split_pdf_by_page_groups(original_pdf_path, page_groups):
    """
    Splits the main PDF into multiple smaller PDFs, one for each logical document
    identified by the AI. The pages in each new PDF are arranged in the
    correct order determined by the `get_correct_page_order` function.
    """
    split_pdf_paths = []
    try:
        with fitz.open(original_pdf_path) as original_doc:
            for i, group in enumerate(page_groups):
                pages_from_ai = group.get('page_order', [])
                if not pages_from_ai:
                    logging.warning(f"Skipping empty page group {i}.")
                    continue
                
                # **NEW ROBUSTNESS CHECK**: This block intelligently parses the list of pages
                # from the AI. It can handle integers (e.g., 3) or strings (e.g., "Page 3"),
                # making the page selection more reliable.
                pages_to_include = []
                for item in pages_from_ai:
                    if isinstance(item, int):
                        pages_to_include.append(item)
                    elif isinstance(item, str):
                        match = re.search(r'\d+', item)
                        if match:
                            pages_to_include.append(int(match.group(0)))
                
                if not pages_to_include:
                    logging.warning(f"Could not extract any valid page numbers for group {i}. Skipping.")
                    continue

                new_doc = fitz.open()
                # Convert 1-based page numbers from AI to 0-based indices for PyMuPDF.
                zero_indexed_pages = [p - 1 for p in pages_to_include]
                
                for page_num in zero_indexed_pages:
                    if 0 <= page_num < original_doc.page_count:
                        new_doc.insert_pdf(original_doc, from_page=page_num, to_page=page_num)

                temp_pdf_path = os.path.join(os.path.dirname(original_pdf_path), f"temp_split_{i}_{os.path.basename(original_pdf_path)}")
                new_doc.save(temp_pdf_path)
                new_doc.close()
                split_pdf_paths.append(temp_pdf_path)
    except Exception as e:
        logging.error(f"Error splitting PDF {original_pdf_path} by page groups: {e}")
    return split_pdf_paths

def perform_ocr_on_pdf(file_path: str) -> tuple[str, fitz.Document | None, int]:
    """
    Processes a PDF file, performing OCR on each page to extract text.
    If a page contains no selectable text, it's treated as an image and OCR'd.
    It returns the full extracted text, a new searchable PDF document object, and the page count.
    """
    page_count = 0
    try:
        with fitz.open(file_path) as doc:
            page_count = doc.page_count
            extracted_text = ""
            new_doc = fitz.open()  # This will be the new, text-searchable PDF.
            for i, page in enumerate(doc): # type: ignore
                page_number = i + 1
                extracted_text += PAGE_MARKER_TEMPLATE.format(page_number)
                
                # Try to get text directly. If it's empty, assume it's an image and use OCR.
                current_page_text = page.get_text().strip()
                if not current_page_text:
                    logging.info(f"Page {page_number} of {os.path.basename(file_path)} has no text layer; performing OCR.")
                    # Increase resolution for better OCR results.
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                    current_page_text = pytesseract.image_to_string(img)
                
                extracted_text += current_page_text
                
                # Create a new page in the output PDF that includes the original image
                # and an invisible text layer, making it searchable.
                new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height) # type: ignore
                pix = page.get_pixmap()
                new_page.insert_image(new_page.rect, stream=io.BytesIO(pix.tobytes("png")))
                new_page.insert_text(page.rect.tl, current_page_text, render_mode=3) # render_mode=3 makes text invisible but searchable

            return extracted_text, new_doc, page_count
    except Exception as e:
        logging.error(f"Error performing OCR on {file_path}: {e}")
        return "", None, page_count

def process_document(file_path, category, title):
    """
    Handles the final processing of a single, split document. This includes:
    - Performing a final OCR pass to create a searchable PDF.
    - Generating a standardized filename.
    - Moving the final PDF to the correct category folder.
    - Saving the searchable OCR version and a Markdown summary report.
    """
    file_name = os.path.basename(file_path)
    logging.info(f"Processing final document '{file_name}' -> Category: {category}, Title: {title}")

    # Although OCR was done on the merged file, we do it again on the split file
    # to create a clean, self-contained searchable PDF and its text content.
    document_text, ocr_doc, _ = perform_ocr_on_pdf(file_path)
    reason = "Success" if document_text else "Text extraction failed during final processing."

    # Sanitize the title provided by the AI to create a valid filename.
    sanitized_title = "".join(c for c in title if c.isalnum() or c in (' ', '.', '-', '_', '(', ')')).rstrip().replace(' ', '_')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Define the names and paths for the final output files.
    new_name = f"{category}_{sanitized_title}_{timestamp}.pdf"
    new_ocr_name = f"{category}_{sanitized_title}_{timestamp}_ocr.pdf"
    markdown_name = f"{category}_{sanitized_title}_{timestamp}.md"
    destination_dir = ABSOLUTE_CATEGORIES.get(category, ABSOLUTE_CATEGORIES["other"])
    destination_path = os.path.join(destination_dir, new_name)
    destination_ocr_path = os.path.join(destination_dir, new_ocr_name)
    markdown_path = os.path.join(destination_dir, markdown_name)

    try:
        if DRY_RUN:
            logging.info(f"[DRY RUN] Would move/process {file_name} to {destination_dir}")
        else:
            # Move the split PDF (which is just the original page images) to its final destination.
            shutil.move(file_path, destination_path)
            logging.info(f"Moved final document to: {destination_path}")

            # Save the new, text-searchable OCR version.
            if ocr_doc:
                ocr_doc.save(destination_ocr_path, garbage=4, deflate=True)
                logging.info(f"Saved OCR copy to: {destination_ocr_path}")
            
            # Create and save a Markdown file with a summary of the processing.
            markdown_content = f"""# Document Analysis Report

## Original File: {file_name}
## Assigned Category: {category}
## Assigned Title: {title}

---

## Extracted Text (OCR)

```
{document_text}
```

---

## Processing Summary
- **Status:** {reason}
- Note: Category and title were determined during the initial batch analysis."""
            with open(markdown_path, "w", encoding="utf-8") as md_file:
                md_file.write(markdown_content)
            logging.info(f"Saved Markdown report to: {markdown_path}")
    except Exception as e:
        logging.error(f"Error saving final files for {file_name}: {e}")
    finally:
        if ocr_doc:
            ocr_doc.close()

# --- Main Logic ---
def main():
    """
    The main function that orchestrates the entire document processing workflow.
    It scans the intake directory, processes all found PDFs, and handles cleanup.
    """
    logging.info(f"Starting document processing scan of {INTAKE_DIR}...")
    cleanup_archive(ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS)

    # Find all PDF files in the intake directory.
    initial_files = [
        os.path.join(INTAKE_DIR, f)
        for f in os.listdir(INTAKE_DIR)
        if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(INTAKE_DIR, f))
    ]
    
    if not initial_files:
        logging.info("No new PDF files found. Scan complete.")
        return

    file_to_process = None
    temp_merged_path = None
    
    # If there are multiple files, merge them. Otherwise, process the single file.
    if len(initial_files) > 1:
        logging.info(f"Found {len(initial_files)} PDF files. Merging them into a single batch for analysis.")
        temp_merged_name = f"temp_mega_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        temp_merged_path = os.path.join(INTAKE_DIR, temp_merged_name)
        file_to_process = merge_pdfs(initial_files, temp_merged_path)
    elif len(initial_files) == 1:
        file_to_process = initial_files[0]
    
    if not file_to_process:
        logging.error("Failed to prepare a file for processing. Original files will be retried on next run.")
        return

    file_name = os.path.basename(file_to_process)
    logging.info(f"--- Starting analysis for: {file_name} ---")
    
    split_docs_paths = []
    processed_successfully = False 
    try:
        # Step 1: Perform OCR on the entire batch file to get all text content.
        full_pdf_text, _, page_count = perform_ocr_on_pdf(file_to_process)

        if full_pdf_text:
            # Step 2: Send the text to the AI for grouping into logical documents.
            document_groups = analyze_and_group_document(full_pdf_text)
            
            if not isinstance(document_groups, list) or not document_groups:
                logging.error(f"AI grouping failed for {file_name}. Halting processing.")
                return

            # Step 3: For each group, determine the correct page order.
            final_sorted_groups = []
            for group in document_groups:
                unordered_pages = group.get('pages', [])
                if not unordered_pages: continue
                
                logging.info(f"Found document group '{group.get('title')}' with {len(unordered_pages)} pages. Determining page order...")
                
                # Create a text "blob" containing only the pages for this specific group.
                group_text_blob = ""
                for page_num in unordered_pages:
                    page_text = get_text_for_page(full_pdf_text, page_num)
                    group_text_blob += PAGE_MARKER_TEMPLATE.format(page_num) + page_text

                # Ask the AI to sort the pages in this group.
                final_order = get_correct_page_order(group_text_blob)
                
                if not final_order:
                    logging.warning(f"Page ordering AI call failed for group '{group.get('title')}'. Using original page order as a fallback.")
                
                final_sorted_groups.append({
                    'category': group.get('category'),
                    'title': group.get('title'),
                    'page_order': final_order if final_order else unordered_pages
                })

            # Step 4: Split the merged PDF into final, sorted documents.
            logging.info(f"Analysis complete. Found {len(final_sorted_groups)} logical document(s).")
            split_docs_paths = split_pdf_by_page_groups(file_to_process, final_sorted_groups)
            
            # Step 5: Process each split document (move, rename, save OCR/Markdown).
            if split_docs_paths:
                for i, doc_path in enumerate(split_docs_paths):
                    category = final_sorted_groups[i].get('category')
                    title = final_sorted_groups[i].get('title')
                    process_document(doc_path, category, title)
                
                processed_successfully = True
        else:
            logging.error(f"Initial OCR failed for {file_name}. Halting processing.")

    except Exception as e:
        logging.critical(f"A critical error occurred while processing {file_name}: {e}")
    finally:
        # --- Cleanup Phase ---
        # This block ensures that all original and temporary files are handled correctly,
        # regardless of whether the processing was successful or not.
        if processed_successfully:
            # If everything worked, archive the original input files.
            for original_file in initial_files:
                if os.path.exists(original_file):
                    if DRY_RUN:
                        logging.info(f"[DRY RUN] Would archive original file: {os.path.basename(original_file)}")
                    else:
                        try:
                            shutil.move(original_file, os.path.join(ARCHIVE_DIR, os.path.basename(original_file)))
                            logging.info(f"Archived original file: {os.path.basename(original_file)}")
                        except Exception as e:
                            logging.error(f"Failed to archive original file {os.path.basename(original_file)}: {e}")
        else:
            # If processing failed, leave the original files in the intake directory
            # so they can be retried on the next run.
            logging.info(f"Processing was not successful. Original files will remain in {INTAKE_DIR} for the next run.")
        
        # Clean up the large temporary file created by merging all the PDFs.
        if temp_merged_path and os.path.exists(temp_merged_path):
            try:
                os.remove(temp_merged_path)
                logging.info(f"Cleaned up temporary merged file: {os.path.basename(temp_merged_path)}")
            except Exception as e:
                logging.error(f"Failed to remove temporary merged file: {e}")

        # Clean up the smaller temporary files created when splitting the merged PDF.
        if split_docs_paths:
            logging.info(f"Cleaning up {len(split_docs_paths)} temporary split files for {file_name}.")
            for temp_path in split_docs_paths:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception as e:
                        logging.error(f"Failed to remove temporary file {temp_path}: {e}")
    
    logging.info("Scan complete.")

if __name__ == "__main__":
    # This allows the script to be run directly from the command line.
    main()

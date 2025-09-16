# document_processor.py (Definitive AI Pipeline Version)
#
# This script uses a robust pipeline:
# 1. EasyOCR provides high-accuracy text and caches models locally.
# 2. A simple AI call classifies each page individually with smart matching.
# 3. Smart Python code groups consecutive pages of the same category.
# 4. Focused AI calls generate a title and correct page order for each group.
# 5. Enhanced logging provides clear status updates during execution.

import os
import shutil
import fitz  # PyMuPDF
from typing import Any
import json
import time
import io
import re
from datetime import datetime, timedelta
from PIL import Image
import logging
import ollama 
import easyocr
import pytesseract
from prompts import CLASSIFICATION_PROMPT_TEMPLATE, TITLING_PROMPT_TEMPLATE, ORDERING_PROMPT

# --- Environment and Configuration ---
try:
    from config import DRY_RUN, OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_CONTEXT_WINDOW, INTAKE_DIR, PROCESSED_DIR, CATEGORIES, LOG_FILE, LOG_LEVEL, ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS, MAX_RETRIES, RETRY_DELAY_SECONDS
except ImportError:
    print("Error: config.py not found or essential variables not set.")
    exit(1)

# --- Logging Setup (Moved to Top) ---
# Logging is configured here, immediately after imports, to ensure it is
# initialized before any other library (like EasyOCR) can set up a default logger.
PAGE_MARKER_TEMPLATE = "\n\n--- Page {} ---\n\n"
log_level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}
logging.basicConfig(level=log_level_map.get(LOG_LEVEL.upper(), logging.INFO), format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler(LOG_FILE) if LOG_FILE else logging.NullHandler(), logging.StreamHandler()])

# --- Initialize External Services ---
try:
    ollama_client = ollama.Client(host=OLLAMA_HOST)
except Exception as e:
    logging.critical(f"Failed to create Ollama client for host {OLLAMA_HOST}. Is Ollama running? Error: {e}")
    exit(1)

try:
    logging.info("Initializing EasyOCR reader... This may take a moment on first run.")
    # Define a permanent path for the model cache within your project.
    model_cache_dir = os.path.join(os.path.dirname(__file__), "model_cache")
    os.makedirs(model_cache_dir, exist_ok=True)
    # Tell EasyOCR to use this directory for storing and loading models.
    ocr_reader = easyocr.Reader(['en'], model_storage_directory=model_cache_dir)
    logging.info("EasyOCR reader initialized successfully.")
except Exception as e:
    logging.critical(f"Failed to initialize EasyOCR. Error: {e}")
    exit(1)


# --- Path Setup ---
ABSOLUTE_CATEGORIES = {category_name: os.path.join(PROCESSED_DIR, relative_path) for category_name, relative_path in CATEGORIES.items()}
for category_path in ABSOLUTE_CATEGORIES.values():
    os.makedirs(category_path, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

def cleanup_archive(directory, retention_days):
    """Deletes files in the archive directory older than the specified retention period."""
    logging.info(f"Starting archive cleanup in {directory}. Deleting files older than {retention_days} days.")
    now = datetime.now()
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            try:
                mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                if (now - mod_time).days > retention_days:
                    if DRY_RUN: logging.info(f"[DRY RUN] Would have deleted old archive file: {file_path}")
                    else:
                        os.remove(file_path)
                        logging.info(f"Deleted old archive file: {file_path}")
            except Exception as e: logging.error(f"Error cleaning up archive file {file_path}: {e}")
    logging.info("Archive cleanup complete.")


# --- LLM and Helper Functions ---
def classify_single_page(page_text: str) -> str:
    """AI Task 1: Takes the text of a single page and returns its category."""
    categories_list_str = "\n".join(f"- {cat}" for cat in CATEGORIES.keys())
    system_prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(categories_list=categories_list_str)
    messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': page_text}]
    options = {'num_ctx': 4096} 
    for attempt in range(MAX_RETRIES):
        try:
            response = ollama_client.chat(model=OLLAMA_MODEL, messages=messages, options=options)
            category = response['message']['content'].strip().lower().replace(" ", "_")
            
            # More robust matching for singular/plural categories.
            if category in CATEGORIES:
                return category
            else:
                for key in CATEGORIES:
                    if category.startswith(key.lower().replace(" ", "_").rstrip('s')):
                        logging.warning(f"AI returned non-standard category '{category}', matched to '{key}'.")
                        return key
                
                logging.warning(f"AI returned unknown category '{category}'. Defaulting to 'other'.")
                return "other"
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Single page classification failed: {e}")
            if attempt < MAX_RETRIES - 1: time.sleep(RETRY_DELAY_SECONDS)
    return "other"

def generate_title_for_group(group_text: str, category: str) -> str:
    """AI Task 2: Creates a concise title for a pre-grouped document."""
    system_prompt = TITLING_PROMPT_TEMPLATE.format(category=category)
    messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': group_text}]
    options = {'num_ctx': OLLAMA_CONTEXT_WINDOW}
    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Generating title for '{category}' group...")
            response = ollama_client.chat(model=OLLAMA_MODEL, messages=messages, options=options)
            return response['message']['content'].strip()
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Titling failed: {e}")
            if attempt < MAX_RETRIES - 1: time.sleep(RETRY_DELAY_SECONDS)
    return "Untitled Document"

def get_correct_page_order(document_group_text: str, original_page_numbers: list[int]) -> list[int] | None:
    """AI Task 3: Takes a single document's text and returns the pages in the correct reading order."""
    system_prompt = ORDERING_PROMPT
    user_query = f"Determine the correct page order for the following document text:\n\n{document_group_text}"
    messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_query}]
    options = {'num_ctx': OLLAMA_CONTEXT_WINDOW}
    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Sending ordering request to Ollama model '{OLLAMA_MODEL}' (Attempt {attempt + 1})...")
            response = ollama_client.chat(model=OLLAMA_MODEL, messages=messages, format='json', options=options)
            response_content = response['message']['content']
            logging.debug(f"Raw Ollama ordering response content:\n---\n{response_content}\n---")
            page_order = json.loads(response_content).get("page_order")
            if page_order and isinstance(page_order, list):
                clean_order: list[int] = []
                for item in page_order:
                    if isinstance(item, int): clean_order.append(item)
                    elif isinstance(item, str):
                        match = re.search(r'\d+', item)
                        if match: clean_order.append(int(match.group(0)))
                return [p for p in clean_order if p in original_page_numbers]
            return None
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Page ordering analysis failed: {e}")
            if attempt < MAX_RETRIES - 1: time.sleep(RETRY_DELAY_SECONDS)
    return None

def get_text_for_page(full_text: str, page_number: int) -> str:
    """Extracts the text for a single page from the concatenated full text string."""
    pattern = re.compile(r'--- Page ' + str(page_number) + r' ---\n(.*?)(?=\n--- Page|\Z)', re.DOTALL)
    match = pattern.search(full_text)
    return match.group(1).strip() if match else ""

# --- PDF Processing Functions ---
def merge_pdfs(pdf_list: list[str], output_path: str) -> str | None:
    """Merges a list of PDFs into a single PDF."""
    logging.info(f"Merging {len(pdf_list)} files into {os.path.basename(output_path)}...")
    result_pdf = fitz.open()
    for pdf_path in pdf_list:
        try:
            with fitz.open(pdf_path) as pdf_doc:
                result_pdf.insert_pdf(pdf_doc)
        except Exception as e:
            logging.error(f"Could not process {pdf_path} during merge: {e}")
    
    result_pdf.save(output_path)
    result_pdf.close()
    return output_path

def perform_ocr_on_pdf(file_path: str) -> tuple[str, int]:
    """Performs OCR using EasyOCR on a PDF, returning its full text and page count."""
    page_count = 0
    try:
        doc: fitz.Document = fitz.open(file_path)
        page_count = doc.page_count
        extracted_text = ""
        for i, page in enumerate(doc):
            page: fitz.Page
            
            page_number = i + 1
            extracted_text += PAGE_MARKER_TEMPLATE.format(page_number)
            current_page_text = (page: Any).get_text().strip()
            if not current_page_text:
                pix = (page: Any).get_pixmap(matrix=fitz.Matrix(2, 2))
                img_bytes = pix.tobytes("png")
                results = ocr_reader.readtext(img_bytes, detail=0, paragraph=True)
                current_page_text = "\n".join([str(item) for item in results]) # type: ignore
            extracted_text += current_page_text
        doc.close()
        return extracted_text, page_count
    except Exception as e:
        logging.error(f"Error performing OCR on {file_path}: {e}")
        return "", page_count
    
def create_output_files(source_pdf_path: str, category: str, title: str):
    """Creates the final OCR'd PDF and Markdown report from a temporary split PDF."""
    file_name = os.path.basename(source_pdf_path)
    logging.info(f"Creating final output files for '{file_name}' -> Category: {category}, Title: {title}")
    
    text_for_report, ocr_doc_obj = "", None
    try:
        doc: fitz.Document = fitz.open(source_pdf_path)
        ocr_doc_obj = fitz.open()
        for page in doc:
            page: fitz.Page

            page_text = page.get_text().strip()
            if not page_text:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
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
            
            new_page = ocr_doc_obj.new_page(width=page.rect.width, height=page.rect.height)
            pix = (page: Any).get_pixmap()
            new_page.insert_image(new_page.rect, stream=io.BytesIO(pix.tobytes("png")))
            new_page.insert_text(page.rect.tl, page_text, render_mode=3)
        doc.close()
        reason = "Success"
    except Exception as e:
        logging.error(f"Error during final OCR pass for {file_name}: {e}")
        reason = "Final OCR pass failed."

    # --- This part of the function remains the same ---
    sanitized_title = "".join(c for c in title if c.isalnum() or c in (' ', '.', '-', '_', '(', ')')).rstrip().replace(' ', '_')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_name_base = f"{category}_{sanitized_title}_{timestamp}"
    destination_dir = ABSOLUTE_CATEGORIES.get(category, ABSOLUTE_CATEGORIES["other"])
    
    original_copy_path = os.path.join(destination_dir, f"{new_name_base}.pdf")
    ocr_copy_path = os.path.join(destination_dir, f"{new_name_base}_ocr.pdf")
    markdown_path = os.path.join(destination_dir, f"{new_name_base}.md")
    
    os.makedirs(destination_dir, exist_ok=True)
    try:
        if DRY_RUN:
            logging.info(f"[DRY RUN] Would create files for {file_name} in {destination_dir}")
        else:
            shutil.copy2(source_pdf_path, original_copy_path)
            logging.info(f"Saved original copy to: {original_copy_path}")
            if ocr_doc_obj:
                ocr_doc_obj.save(ocr_copy_path, garbage=4, deflate=True)
                logging.info(f"Saved OCR copy to: {ocr_copy_path}")
            markdown_content = f"""# Document Analysis Report\n\n## Source File: {file_name}\n## Assigned Category: {category}\n## Assigned Title: {title}\n\n---\n\n## Extracted Text (OCR)\n\n```\n{text_for_report.strip()}\n```\n\n---\n\n## Processing Summary\n- **Status:** {reason}"""
            with open(markdown_path, "w", encoding="utf-8") as md_file:
                md_file.write(markdown_content)
            logging.info(f"Saved Markdown report to: {markdown_path}")
    except Exception as e:
        logging.error(f"Error saving final files for {file_name}: {e}")
    finally:
        if ocr_doc_obj:
            ocr_doc_obj.close()

def split_and_process_pdf(original_pdf_path: str, final_documents: list[dict]):
    """Splits the source PDF and sends each new temp file for final processing."""
    temp_files_to_clean = []
    try:
        original_doc: fitz.Document = fitz.open(original_pdf_path)
        for i, doc_details in enumerate(final_documents):
            pages_to_include = doc_details.get('page_order', [])
            category = doc_details.get('category')
            title = doc_details.get('title')
            if not pages_to_include or not category or not title:
                logging.warning(f"Skipping incomplete document group #{i}.")
                continue
            
            new_doc = fitz.open()
            zero_indexed_pages = [p - 1 for p in pages_to_include]
            for page_num in zero_indexed_pages:
                if 0 <= page_num < original_doc.page_count:
                    new_doc.insert_pdf(original_doc, from_page=page_num, to_page=page_num)

            temp_pdf_path = os.path.join(os.path.dirname(original_pdf_path), f"temp_split_{i}_{os.path.basename(original_pdf_path)}")
            new_doc.save(temp_pdf_path)
            new_doc.close()
            temp_files_to_clean.append(temp_pdf_path)
            
            create_output_files(temp_pdf_path, category, title)
        original_doc.close()
        return temp_files_to_clean
    except Exception as e:
        logging.error(f"Error during splitting and processing for {original_pdf_path}: {e}")
        return temp_files_to_clean
    
# --- Main Logic ---
def main():
    """Main function that orchestrates the AI Pipeline workflow."""
    logging.info("\n" + "="*60 + "\n========== STARTING NEW DOCUMENT PROCESSING RUN ==========\n" + "="*60)
    cleanup_archive(ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS)
    
    # --- STAGE 1 of 5: Preparing Batch File ---
    logging.info("--- STAGE 1 of 5: Preparing Batch File ---")
    initial_files = [os.path.join(INTAKE_DIR, f) for f in os.listdir(INTAKE_DIR) if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(INTAKE_DIR, f))]
    if not initial_files:
        logging.info("No new PDF files found. Scan complete.")
        return

    file_to_process = None
    temp_merged_path = None
    
    if len(initial_files) > 1:
        logging.info(f"Found {len(initial_files)} PDF files. Merging them into a single batch.")
        temp_merged_name = f"temp_mega_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        temp_merged_path = os.path.join(INTAKE_DIR, temp_merged_name)
        file_to_process = merge_pdfs(initial_files, temp_merged_path)
    elif len(initial_files) == 1:
        logging.info("Found 1 PDF file. Processing it directly.")
        file_to_process = initial_files[0]
    
    if not file_to_process:
        logging.error("Failed to prepare a file for processing.")
        return
    logging.info("--- STAGE 1 COMPLETE ---")
    
    file_name = os.path.basename(file_to_process)
    logging.info(f"\n***************** PROCESSING BATCH: {file_name} *****************")
    
    processed_successfully = False
    temp_split_paths: list[str] = []
    try:
        # --- STAGE 2 of 5: Performing Initial OCR on Batch ---
        logging.info("--- STAGE 2 of 5: Performing Initial OCR on Batch ---")
        full_pdf_text, page_count = perform_ocr_on_pdf(file_to_process)
        if not full_pdf_text:
            logging.error(f"Initial OCR failed for {file_name}. Halting.")
            return

        # --- STAGE 3 of 5: Classifying Pages (AI Task) ---
        logging.info("--- STAGE 3 of 5: Classifying Pages (AI Task) ---")
        page_classifications = []
        for i in range(1, page_count + 1):
            page_text = get_text_for_page(full_pdf_text, i)
            if not page_text.strip():
                logging.warning(f"Page {i} has no text, skipping classification.")
                page_classifications.append({'page_num': i, 'category': 'other'})
                continue
            
            logging.info(f"Classifying page {i}/{page_count}...")
            category = classify_single_page(page_text)
            page_classifications.append({'page_num': i, 'category': category})
        
        logging.info("--- STAGE 3 COMPLETE ---")
        logging.debug(f"Classification results: {page_classifications}")

        # --- STAGE 4 of 5: Grouping, Titling, and Ordering Documents ---
        logging.info("--- STAGE 4 of 5: Grouping, Titling, and Ordering ---")
        if not page_classifications:
            logging.warning(f"No pages were classified for {file_name}. Halting.")
            return

        document_groups: list[dict] = []
        if page_classifications:
            current_group_pages = [page_classifications[0]['page_num']]
            current_category = page_classifications[0]['category']

            for i in range(1, len(page_classifications)):
                page_num, category = page_classifications[i]['page_num'], page_classifications[i]['category']
                if category == current_category:
                    current_group_pages.append(page_num)
                else:
                    document_groups.append({'category': current_category, 'pages': current_group_pages})
                    current_group_pages = [page_num]
                    current_category = category
            document_groups.append({'category': current_category, 'pages': current_group_pages})

        logging.info(f"Found {len(document_groups)} logical document(s) based on classification blocks.")

        final_documents = []
        for group in document_groups:
            pages = group['pages']
            category = group['category']
            
            group_text_blob = ""
            for page_num in pages:
                group_text_blob += PAGE_MARKER_TEMPLATE.format(page_num) + get_text_for_page(full_pdf_text, page_num)
            
            title = generate_title_for_group(group_text_blob, category)
            page_order = get_correct_page_order(group_text_blob, pages)
            
            final_documents.append({
                'category': category,
                'title': title,
                'page_order': page_order if page_order else pages
            })
        logging.info("--- STAGE 4 COMPLETE ---")

        # --- STAGE 5 of 5: Splitting and Creating Final Files ---
        logging.info("--- STAGE 5 of 5: Splitting and Creating Final Files ---")
        temp_split_paths = split_and_process_pdf(file_to_process, final_documents)
        logging.info("--- STAGE 5 COMPLETE ---")

        processed_successfully = True

    except Exception as e:
        logging.critical(f"A critical error occurred while processing {file_name}: {e}")
    finally:
        # --- Final Cleanup ---
        if processed_successfully:
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
            logging.info(f"Processing for {file_name} was not successful. It will remain in {INTAKE_DIR} for the next run.")
        
        if temp_merged_path and os.path.exists(temp_merged_path):
            try: os.remove(temp_merged_path)
            except Exception as e: logging.error(f"Failed to remove temporary merged file: {e}")
        
        if temp_split_paths:
            for temp_path in temp_split_paths:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception as e:
                        logging.error(f"Failed to remove temporary file {temp_path}: {e}")
    
    logging.info(f"***************** FINISHED PROCESSING BATCH: {file_name} *****************")
    logging.info("\n" + "="*60 + "\n============== DOCUMENT PROCESSING RUN COMPLETE ==============\n" + "="*60)

if __name__ == "__main__":
    main()
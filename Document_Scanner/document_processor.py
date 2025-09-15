# document_processor.py
#
# This script is a robust, production-ready tool for processing PDF documents.
# It merges multiple input files, uses a secure environment variable for the API key,
# and uses externalized prompts for maintainability. The 2-step AI process ensures
# high accuracy for both document grouping and page ordering.

import os
import shutil
import fitz  # PyMuPDF
import json
import time
import requests
import io
import re
from datetime import datetime, timedelta
import pytesseract
from PIL import Image
import logging
from prompts import GROUPING_PROMPT_TEMPLATE, ORDERING_PROMPT

# --- Environment Configuration ---
API_KEY = os.getenv("GEMINI_API_KEY")

try:
    from config import DRY_RUN, API_URL, INTAKE_DIR, PROCESSED_DIR, CATEGORIES, LOG_FILE, LOG_LEVEL, ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS, MAX_RETRIES, RETRY_DELAY_SECONDS
except ImportError:
    print("Error: config.py not found or essential variables not set.")
    exit(1)

# --- Constants ---
PAGE_MARKER_TEMPLATE = "\n\n--- Page {} ---\n\n"

# --- Logging Setup ---
log_level_map = {
    "DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING,
    "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL
}
logging.basicConfig(
    level=log_level_map.get(LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE) if LOG_FILE else logging.NullHandler(),
        logging.StreamHandler()
    ]
)

# --- Path and Category Setup ---
ABSOLUTE_CATEGORIES = {
    category_name: os.path.join(PROCESSED_DIR, relative_path)
    for category_name, relative_path in CATEGORIES.items()
}
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
                    if DRY_RUN:
                        logging.info(f"[DRY RUN] Would have deleted old archive file: {file_path}")
                    else:
                        os.remove(file_path)
                        logging.info(f"Deleted old archive file: {file_path}")
            except Exception as e:
                logging.error(f"Error cleaning up archive file {file_path}: {e}")
    logging.info("Archive cleanup complete.")

# --- LLM Functions ---
def analyze_and_group_document(document_text):
    """AI CALL #1: Groups pages by content and assigns a category and title."""
    if not API_KEY:
        logging.error("API_KEY environment variable not set.")
        return []

    categories_list = ', '.join(CATEGORIES.keys())
    system_prompt = GROUPING_PROMPT_TEMPLATE.format(categories_list=categories_list)
    user_query = f"Analyze and group the documents in the following text:\n\n{document_text}"
    
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
                        "category": {"type": "STRING"},
                        "title": {"type": "STRING"},
                        "pages": {"type": "ARRAY", "items": {"type": "INTEGER"}}
                    },
                    "required": ["category", "title", "pages"]
                }
            }
        },
    }
    headers = {'Content-Type': 'application/json'}
    params = {'key': API_KEY}

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, params=params)
            response.raise_for_status()
            result = response.json()
            if result and 'candidates' in result and result['candidates'][0].get('content'):
                response_json_str = result['candidates'][0]['content']['parts'][0]['text']
                return json.loads(response_json_str)
        except (requests.exceptions.RequestException, json.JSONDecodeError, IndexError, KeyError) as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Document grouping analysis failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
    return []

def get_correct_page_order(document_group_text):
    """AI CALL #2: Takes text of a single document and returns the pages in the correct reading order."""
    if not API_KEY:
        logging.error("API_KEY environment variable not set.")
        return None

    system_prompt = ORDERING_PROMPT
    user_query = f"Determine the correct page order for the following document text:\n\n{document_group_text}"

    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "page_order": {"type": "ARRAY", "items": {"type": "INTEGER"}}
                },
                "required": ["page_order"]
            }
        },
    }
    headers = {'Content-Type': 'application/json'}
    params = {'key': API_KEY}

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, params=params)
            response.raise_for_status()
            result = response.json()
            if result and 'candidates' in result and result['candidates'][0].get('content'):
                response_json_str = result['candidates'][0]['content']['parts'][0]['text']
                return json.loads(response_json_str).get("page_order")
        except (requests.exceptions.RequestException, json.JSONDecodeError, IndexError, KeyError) as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Page ordering analysis failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
    return None

# --- PYTHON HELPER FUNCTIONS ---
def get_text_for_page(full_text, page_number):
    """Extracts the text for a single page from the full OCR text blob."""
    start_marker = PAGE_MARKER_TEMPLATE.format(page_number).strip()
    pattern = re.compile(re.escape(start_marker) + r'\n(.*?)(?=\n--- Page|\Z)', re.DOTALL)
    match = pattern.search(full_text)
    return match.group(1).strip() if match else ""

def merge_pdfs(pdf_paths, output_path):
    """
    Merges multiple PDF files into a single PDF file.
    """
    try:
        merged_doc = fitz.open()
        for pdf_path in pdf_paths:
            doc = fitz.open(pdf_path)
            merged_doc.insert_pdf(doc)
            doc.close()
        merged_doc.save(output_path)
        merged_doc.close()
        logging.info(f"Successfully merged {len(pdf_paths)} PDFs into temporary file: {os.path.basename(output_path)}")
        return output_path
    except Exception as e:
        logging.error(f"Error merging PDFs: {e}")
        return None

# --- PDF Processing Functions ---
def split_pdf_by_page_groups(original_pdf_path, page_groups):
    """Splits a PDF into multiple new PDFs based on the final, sorted page_order list."""
    split_pdf_paths = []
    try:
        original_doc: fitz.Document = fitz.open(original_pdf_path)
        for i, group in enumerate(page_groups):
            pages_to_include = group.get('page_order', [])
            if not pages_to_include:
                logging.warning(f"Skipping empty page group {i}.")
                continue
            
            new_doc: fitz.Document = fitz.open()
            zero_indexed_pages = [p - 1 for p in pages_to_include]
            
            for page_num in zero_indexed_pages:
                new_doc.insert_pdf(original_doc, from_page=page_num, to_page=page_num)

            temp_pdf_path = os.path.join(os.path.dirname(original_pdf_path), f"temp_split_{i}_{os.path.basename(original_pdf_path)}")
            new_doc.save(temp_pdf_path)
            new_doc.close()
            split_pdf_paths.append(temp_pdf_path)
        original_doc.close()
    except Exception as e:
        logging.error(f"Error splitting PDF {original_pdf_path} by page groups: {e}")
    return split_pdf_paths

def perform_ocr_on_pdf(file_path: str) -> tuple[str, fitz.Document | None, int]:
    """
    Performs OCR on a PDF, returning its text, a new searchable PDF document, and the page count.
    """
    page_count = 0
    try:
        doc: fitz.Document = fitz.open(file_path)
        page_count = doc.page_count
        extracted_text = ""
        new_doc: fitz.Document = fitz.open()
        for i, page in enumerate(doc): # type: ignore
            page_number = i + 1
            extracted_text += PAGE_MARKER_TEMPLATE.format(page_number)
            current_page_text = page.get_text()
            if not current_page_text.strip():
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                current_page_text = pytesseract.image_to_string(img)
            extracted_text += current_page_text
            
            new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height) # type: ignore
            pix = page.get_pixmap()
            new_page.insert_image(new_page.rect, stream=io.BytesIO(pix.tobytes("png")))
            new_page.insert_text(page.rect.tl, current_page_text)
        doc.close()
        return extracted_text, new_doc, page_count
    except Exception as e:
        logging.error(f"Error performing OCR on {file_path}: {e}")
        return "", None, page_count

def process_document(file_path, category, title):
    """
    Takes a single, logical document (now always a temporary file),
    creates its final versions, and moves them to the correct category folder.
    """
    file_name = os.path.basename(file_path)
    logging.info(f"Processing final document '{file_name}' -> Category: {category}, Title: {title}")

    document_text, ocr_doc, _ = perform_ocr_on_pdf(file_path)
    if not document_text:
        logging.warning(f"Could not extract text from {file_name} during final processing.")
        reason = "Text extraction failed during final processing."
    else:
        reason = "Success"

    sanitized_title = "".join(c for c in title if c.isalnum() or c in (' ', '.', '-', '_', '(', ')')).rstrip().replace(' ', '_')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
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
            shutil.move(file_path, destination_path)
            logging.info(f"Moved final document to: {destination_path}")

            if ocr_doc:
                ocr_doc.save(destination_ocr_path, garbage=4, deflate=True)
                logging.info(f"Saved OCR copy to: {destination_ocr_path}")
            
            markdown_content = f"""# Document Analysis Report\n\n## Original File: {file_name}\n## Assigned Category: {category}\n## Assigned Title: {title}\n\n---\n\n## Extracted Text (OCR)\n\n```\n{document_text}\n```\n\n---\n\n## Processing Summary\n- **Status:** {reason}\n- Note: Category and title were determined during the initial batch analysis."""
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
    """Main function to scan the intake directory and process all PDF files."""
    logging.info(f"Starting document processing scan of {INTAKE_DIR}...")
    cleanup_archive(ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS)

    # Get a list of all PDF files to be processed.
    initial_files = [
        os.path.join(INTAKE_DIR, f)
        for f in os.listdir(INTAKE_DIR)
        if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(INTAKE_DIR, f))
    ]
    
    if not initial_files:
        logging.info("No new PDF files found. Scan complete.")
        return

    # --- NEW: Mega-Merge Logic ---
    file_to_process = None
    temp_merged_path = None
    
    if len(initial_files) > 1:
        logging.info(f"Found {len(initial_files)} PDF files. Merging them into a single batch for analysis.")
        # Create a temporary path for the merged PDF in the intake directory.
        temp_merged_name = f"temp_mega_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        temp_merged_path = os.path.join(INTAKE_DIR, temp_merged_name)
        # Merge all found PDFs into the temporary file.
        file_to_process = merge_pdfs(initial_files, temp_merged_path)
    elif len(initial_files) == 1:
        logging.info("Found 1 PDF file. Processing it directly.")
        file_to_process = initial_files[0]
    
    # If there's nothing to process (e.g., merge failed), exit.
    if not file_to_process:
        logging.error("Failed to prepare a file for processing. Aborting run.")
        return

    # This is the main processing block, now operating on a single file (either original or merged).
    file_name = os.path.basename(file_to_process)
    logging.info(f"--- Starting analysis for: {file_name} ---")
    
    split_docs_paths = []
    try:
        full_pdf_text, _, page_count = perform_ocr_on_pdf(file_to_process)

        if full_pdf_text:
            document_groups = analyze_and_group_document(full_pdf_text)
            
            if not isinstance(document_groups, list) or not document_groups:
                logging.warning(f"AI grouping failed for {file_name}. Treating as a single document.")
                document_groups = [{'category': 'other', 'title': file_name, 'pages': list(range(1, page_count + 1))}]

            final_sorted_groups = []
            for group in document_groups:
                unordered_pages = group.get('pages', [])
                if not unordered_pages: continue
                
                logging.info(f"Found document group '{group.get('title')}' with {len(unordered_pages)} pages. Now determining correct page order...")
                
                group_text_blob = ""
                for page_num in unordered_pages:
                    page_text = get_text_for_page(full_pdf_text, page_num)
                    group_text_blob += PAGE_MARKER_TEMPLATE.format(page_num) + page_text

                final_order = get_correct_page_order(group_text_blob)
                
                if not final_order:
                    logging.warning(f"Page ordering AI call failed for group '{group.get('title')}'. Using original page order.")
                
                final_sorted_groups.append({
                    'category': group.get('category', 'other'),
                    'title': group.get('title', 'untitled'),
                    'page_order': final_order if final_order else unordered_pages
                })

            logging.info(f"Analysis complete. Found {len(final_sorted_groups)} logical document(s).")
            split_docs_paths = split_pdf_by_page_groups(file_to_process, final_sorted_groups)
            
            if split_docs_paths:
                for i, doc_path in enumerate(split_docs_paths):
                    category = final_sorted_groups[i].get('category', 'other')
                    title = final_sorted_groups[i].get('title', 'untitled')
                    process_document(doc_path, category, title)
        else:
            logging.error(f"Initial OCR failed for {file_name}. Original files will be archived.")

    except Exception as e:
        logging.critical(f"A critical error occurred while processing {file_name}: {e}")
    finally:
        # After all processing, archive the ORIGINAL files and clean up temporary files.
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
        
        # Clean up the temporary merged file if it was created.
        if temp_merged_path and os.path.exists(temp_merged_path):
            try:
                os.remove(temp_merged_path)
                logging.info(f"Cleaned up temporary merged file: {os.path.basename(temp_merged_path)}")
            except Exception as e:
                logging.error(f"Failed to remove temporary merged file: {e}")

        # Clean up temporary split files.
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
    main()
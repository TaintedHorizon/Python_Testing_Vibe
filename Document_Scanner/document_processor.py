# document_processor.py
#
# This script automates the processing, categorization, and archiving of PDF documents.
# It uses a two-step AI process: first to group documents, then a second, focused
# call for each group to determine the correct page order.

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

# --- Environment Configuration ---
# Imports necessary variables from a separate config.py file.
# This keeps sensitive data like API keys and user-specific paths out of the main script.
try:
    from config import API_KEY, DRY_RUN, API_URL, INTAKE_DIR, PROCESSED_DIR, CATEGORIES, LOG_FILE, LOG_LEVEL, ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS, MAX_RETRIES, RETRY_DELAY_SECONDS
except ImportError:
    print("Error: config.py not found or essential variables not set.")
    exit(1)

# --- Logging Setup ---
# Configures the logging system to output messages to both a file and the console.
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
# Creates absolute paths for all category directories and ensures they exist.
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
    """
    **AI CALL #1**: Groups pages by content and assigns a category and title.
    This prompt's primary job is to correctly separate the pages into logical document "packets".
    """
    if not API_KEY:
        logging.error("API_KEY is not set.")
        return []

    categories_list = ', '.join(CATEGORIES.keys())
    system_prompt = f"""You are an expert document analysis and segmentation assistant. Your task is to analyze text from a multi-page PDF where each page is marked with '--- Page X ---'.

Your goal is to group pages into distinct logical documents. For each document, you will provide its category, a title, and a list of all its physical page numbers.

### CRITICAL RULES:
- **Group by Overall Program/Event (The "Packet" Rule)**: Your most important task is to group all pages related to a single program or event, even if the pages have different sub-topics or are for different audiences (e.g., students vs. parents). For example, a "Confirmation Program" document should include the syllabus, schedule, policies, and any related materials for parents, as these all form a single, cohesive information packet.
- **Separate Truly Different Documents**: As a supporting rule, documents with clearly different primary purposes (like an "Invoice" versus "Boarding Passes") should be treated as separate documents, even if they are for the same event.
- **Every physical page** from the input text **MUST be assigned to exactly ONE** document group.

### JSON Structure for each document:
- `category`: (string) One of: {categories_list}.
- `title`: (string) A concise, human-readable title (max 10 words).
- `pages`: (array of integers) A list of all physical page numbers in this document.
"""
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
    params = {'key': API_KEY} if API_KEY else {}

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
    """
    **AI CALL #2**: Takes the text of a single document and asks the AI to return the pages in order.
    This is a focused task, making it more accurate than trying to group and order simultaneously.
    """
    if not API_KEY:
        logging.error("API_KEY is not set.")
        return None

    system_prompt = """You are a page ordering assistant. You will be given text from a single logical document, where each page is marked with a '--- Page X ---' marker. The physical page numbers (e.g., the 'X' in '--- Page X ---') are from the original scan and may not be sequential. Your only task is to determine the correct logical reading order.

- Prioritize any explicit printed page numbers (e.g., "Page 1 of 3", or a number '3' at the bottom of a page) as the most important signal for sorting.
- If no page numbers exist, use contextual clues like dates or logical flow to determine the best order.
- Your response must be a JSON object containing a single key "page_order" with a list of the physical page numbers sorted correctly.
"""
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
    params = {'key': API_KEY} if API_KEY else {}

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

# --- PYTHON HELPER FUNCTION ---
def get_text_for_page(full_text, page_number):
    """Extracts the text for a single page from the full OCR text blob."""
    # This pattern finds the text between '--- Page X ---' and the next page marker or the end of the string.
    pattern = re.compile(r'--- Page ' + str(page_number) + r' ---\n(.*?)(?=\n--- Page|\Z)', re.DOTALL)
    match = pattern.search(full_text)
    return match.group(1).strip() if match else ""

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
            # Convert to 0-indexed page numbers for PyMuPDF.
            zero_indexed_pages = [p - 1 for p in pages_to_include]
            
            for page_num in zero_indexed_pages:
                new_doc.insert_pdf(original_doc, from_page=page_num, to_page=page_num)

            # Create a temporary file that will be processed further.
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
        # The '# type: ignore' comments suppress persistent, incorrect warnings from the Pylance extension.
        for i, page in enumerate(doc): # type: ignore
            page_number = i + 1
            extracted_text += f"\n\n--- Page {page_number} ---\n\n"
            current_page_text = page.get_text()
            # If a page has no text (it's an image), perform OCR on it.
            if not current_page_text.strip():
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # Render at 2x resolution for better quality
                img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                current_page_text = pytesseract.image_to_string(img)
            extracted_text += current_page_text
            
            # Create a new page, copy the original image, and add the OCR text as an invisible layer.
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
    Takes a single, logical document (now always a temporary file from the splitter),
    creates its final versions (original, OCR'd copy, Markdown report), and moves them
    to the correct category folder.
    """
    file_name = os.path.basename(file_path)
    logging.info(f"Processing final document '{file_name}' -> Category: {category}, Title: {title}")

    # Perform final OCR to get the text for the report and the searchable PDF object.
    document_text, ocr_doc, _ = perform_ocr_on_pdf(file_path)
    if not document_text:
        logging.warning(f"Could not extract text from {file_name} during final processing.")
        reason = "Text extraction failed during final processing."
    else:
        reason = "Success"

    # Sanitize the AI-generated title for use in a filename.
    sanitized_title = "".join(c for c in title if c.isalnum() or c in (' ', '.', '-', '_', '(', ')')).rstrip().replace(' ', '_')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Define all final filenames and paths.
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
            # Move the temporary file to its final destination with the new, descriptive name.
            shutil.move(file_path, destination_path)
            logging.info(f"Moved final document to: {destination_path}")

            # Save the searchable OCR'd copy.
            if ocr_doc:
                ocr_doc.save(destination_ocr_path, garbage=4, deflate=True)
                logging.info(f"Saved OCR copy to: {destination_ocr_path}")
            
            # Create and save the Markdown report.
            markdown_content = f"""# Document Analysis Report\n\n## Original File: {file_name}\n## Assigned Category: {category}\n## Assigned Title: {title}\n\n---\n\n## Extracted Text (OCR)\n\n```\n{document_text}\n```\n\n---\n\n## Processing Summary\n- **Status:** {reason}\n- Note: Category and title were determined during the initial batch analysis."""
            with open(markdown_path, "w", encoding="utf-8") as md_file:
                md_file.write(markdown_content)
            logging.info(f"Saved Markdown report to: {markdown_path}")
    except Exception as e:
        logging.error(f"Error saving final files for {file_name}: {e}")
    finally:
        # Ensure the OCR document object is always closed to free up resources.
        if ocr_doc:
            ocr_doc.close()

# --- Main Logic ---
def main():
    """Main function to scan the intake directory and process all PDF files."""
    logging.info(f"Starting document processing scan of {INTAKE_DIR}...")
    cleanup_archive(ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS)

    # Get a list of all PDF files to be processed.
    files_to_process = [
        os.path.join(INTAKE_DIR, f)
        for f in os.listdir(INTAKE_DIR)
        if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(INTAKE_DIR, f))
    ]
    
    if not files_to_process:
        logging.info("No new PDF files found. Scan complete.")
        return

    # Process each PDF file found.
    for file_path in files_to_process:
        file_name = os.path.basename(file_path)
        logging.info(f"--- Starting analysis for: {file_name} ---")
        
        split_docs_paths = []
        try:
            # Step 1: Perform an initial OCR on the entire source file to get its full text.
            full_pdf_text, _, page_count = perform_ocr_on_pdf(file_path)

            if full_pdf_text:
                # Step 2: Make the first AI call to get the document groups (category, title, and unordered pages).
                document_groups = analyze_and_group_document(full_pdf_text)
                
                # If the AI fails, create a "dummy" group to process the file as a single document.
                if not isinstance(document_groups, list) or not document_groups:
                    logging.warning(f"AI grouping failed for {file_name}. Treating as a single document.")
                    document_groups = [{'category': 'other', 'title': file_name, 'pages': list(range(1, page_count + 1))}]

                final_sorted_groups = []
                # Step 3: Loop through each group and make a second, focused AI call just for ordering.
                for group in document_groups:
                    unordered_pages = group.get('pages', [])
                    if not unordered_pages:
                        continue
                    
                    logging.info(f"Found document group '{group.get('title')}' with {len(unordered_pages)} pages. Now determining correct page order...")
                    
                    # Create a smaller text blob containing only the pages for this specific group.
                    group_text_blob = ""
                    for page_num in unordered_pages:
                        page_text = get_text_for_page(full_pdf_text, page_num)
                        group_text_blob += f"\n\n--- Page {page_num} ---\n\n" + page_text

                    # Make the second AI call to get the final page order.
                    final_order = get_correct_page_order(group_text_blob)
                    
                    # If the ordering call fails, gracefully fall back to the original order from the grouping step.
                    if not final_order:
                        logging.warning(f"Page ordering AI call failed for group '{group.get('title')}'. Using original page order.")
                    
                    # Store the final, correctly ordered group information.
                    final_sorted_groups.append({
                        'category': group.get('category', 'other'),
                        'title': group.get('title', 'untitled'),
                        'page_order': final_order if final_order else unordered_pages
                    })

                # Step 4: Split the original PDF into temporary files using the final, sorted page lists.
                logging.info(f"Analysis complete. Found {len(final_sorted_groups)} logical document(s).")
                split_docs_paths = split_pdf_by_page_groups(file_path, final_sorted_groups)
                
                # Step 5: Process each temporary split file into its final form.
                if split_docs_paths:
                    for i, doc_path in enumerate(split_docs_paths):
                        category = final_sorted_groups[i].get('category', 'other')
                        title = final_sorted_groups[i].get('title', 'untitled')
                        process_document(doc_path, category, title)
            else:
                logging.error(f"Initial OCR failed for {file_name}. It will be archived without processing.")

        except Exception as e:
            logging.critical(f"A critical error occurred while processing {file_name}: {e}")
        finally:
            # Step 6 (Cleanup): This block runs regardless of success or failure.
            # It ensures the original file is always archived and temporary files are cleaned up.
            if os.path.exists(file_path):
                if DRY_RUN:
                    logging.info(f"[DRY RUN] Would archive original file: {file_name}")
                else:
                    try:
                        shutil.move(file_path, os.path.join(ARCHIVE_DIR, file_name))
                        logging.info(f"Archived original file: {file_name}")
                    except Exception as e:
                        logging.error(f"Failed to archive original file {file_name}: {e}")

            if split_docs_paths:
                logging.info(f"Cleaning up {len(split_docs_paths)} temporary split files for {file_name}.")
                for temp_path in split_docs_paths:
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except Exception as e:
                            logging.error(f"Failed to remove temporary file {temp_path}: {e}")
    
    logging.info("Scan complete.")

# This ensures the main() function is called when the script is run directly.
if __name__ == "__main__":
    main()
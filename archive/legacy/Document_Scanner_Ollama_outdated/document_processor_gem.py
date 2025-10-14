# document_processor.py (Definitive AI Pipeline Version with All Fixes and Improvements)

import os
import shutil
import fitz
import json
import time
import io
import re
from datetime import datetime, timedelta
from PIL import Image
import logging
import warnings
import ollama
import easyocr
import pytesseract
from prompts import CLASSIFICATION_PROMPT_TEMPLATE, TITLING_PROMPT_TEMPLATE, ORDERING_PROMPT

# --- Environment and Configuration ---
try:
    from config import DRY_RUN, OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_CONTEXT_WINDOW, INTAKE_DIR, PROCESSED_DIR, CATEGORIES, LOG_FILE, LOG_LEVEL, ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS, MAX_RETRIES, RETRY_DELAY_SECONDS
except ImportError:
    print("CRITICAL ERROR: 'config.py' not found.")
    exit(1)

# --- Logging Setup (Moved to Top) ---
PAGE_MARKER_TEMPLATE = "\n\n--- Page {} ---\n\n"
log_level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}

# Get the root logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)  # Set the lowest level to capture everything

# Create a formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Create a file handler
if LOG_FILE:
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(log_level_map.get(LOG_LEVEL.upper(), logging.DEBUG))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

# Create a stream handler for the console
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)  # Set the level for console output
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
logging.getLogger("pytesseract").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("easyocr").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
# --- Suppress Specific Warnings ---
# This will hide the specific "pin_memory" UserWarning from PyTorch.
warnings.filterwarnings(
    "ignore",
    message=".*'pin_memory' argument is set as true but no accelerator is found.*"
)

# --- Initialize External Services ---
try:
    ollama_client = ollama.Client(host=OLLAMA_HOST)
    logging.info(f"Successfully connected to Ollama client at host: {OLLAMA_HOST}")
except Exception as e:
    logging.critical(f"Failed to create Ollama client for host '{OLLAMA_HOST}'. Error: {e}")
    exit(1)

try:
    logging.info("Initializing EasyOCR reader... This may take a moment on first run.")
    model_cache_dir = os.path.join(os.path.dirname(__file__), "model_cache")
    os.makedirs(model_cache_dir, exist_ok=True)
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
logging.info("Verified and created all necessary processing and archive directories.")

def cleanup_archive(directory: str, retention_days: int):
    logging.info(f"Starting archive cleanup in '{directory}'. Deleting files older than {retention_days} days.")
    now = datetime.now()
    retention_limit = now - timedelta(days=retention_days)
    try:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                try:
                    mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if mod_time < retention_limit:
                        if DRY_RUN:
                            logging.info(f"[DRY RUN] Would have deleted old archive file: {file_path}")
                        else:
                            os.remove(file_path)
                            logging.info(f"Deleted old archive file: {file_path}")
                except Exception as e:
                    logging.error(f"Error processing archive file '{file_path}' for cleanup: {e}")
    except Exception as e:
        logging.error(f"Failed to list files in archive directory '{directory}': {e}")
    logging.info("Archive cleanup complete.")

# --- LLM and Helper Functions ---
def classify_single_page(page_text: str, recent_categories: list[str]) -> str:
    categories_list_str = "\n".join(f"- {cat}" for cat in CATEGORIES.keys())
    recent_categories_str = ", ".join(f"'{cat}'" for cat in recent_categories) if recent_categories else "None yet"
    system_prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(categories_list=categories_list_str, recent_categories=recent_categories_str)
    messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': page_text}]
    # Respect OLLAMA_NUM_GPU env value (if set) so external scripts can request CPU-only.
    try:
        env_num = os.getenv('OLLAMA_NUM_GPU')
        num_gpu_val = int(env_num) if env_num is not None else 0
    except Exception:
        num_gpu_val = 0
    options = {'num_ctx': 4096, 'num_gpu': num_gpu_val}
    for attempt in range(MAX_RETRIES):
        try:
            response = ollama_client.chat(model=OLLAMA_MODEL, messages=messages, options=options)
            category = response['message']['content'].strip()
            for key in CATEGORIES:
                if category.lower().replace(" ", "_") == key.lower().replace(" ", "_"):
                    return key
            logging.warning(f"AI returned unknown category '{category}'. Defaulting to 'other'.")
            return "other"
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Single page classification failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
    return "other"

def generate_title_and_subcategory(group_text: str, category: str) -> tuple[str, str]:
    system_prompt = TITLING_PROMPT_TEMPLATE.format(category=category)
    messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': group_text}]
    try:
        env_num = os.getenv('OLLAMA_NUM_GPU')
        num_gpu_val = int(env_num) if env_num is not None else 0
    except Exception:
        num_gpu_val = 0
    options = {'num_ctx': OLLAMA_CONTEXT_WINDOW, 'num_gpu': num_gpu_val}
    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Generating title/subcategory for '{category}' group...")
            response = ollama_client.chat(model=OLLAMA_MODEL, messages=messages, format='json', options=options)
            response_content = response['message']['content']
            data = json.loads(response_content)
            sub_category = data.get("sub_category", "Unknown")
            title = data.get("title", "Untitled Document")
            return sub_category, title
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Titling/sub-categorization failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
    return "other", "Untitled Document"

def get_correct_page_order(document_group_text: str, original_page_numbers: list[int]) -> list[int]:
    system_prompt = ORDERING_PROMPT
    user_query = f"Determine the correct page order for the following document text:\n\n{document_group_text}"
    messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_query}]
    try:
        env_num = os.getenv('OLLAMA_NUM_GPU')
        num_gpu_val = int(env_num) if env_num is not None else 0
    except Exception:
        num_gpu_val = 0
    options = {'num_ctx': OLLAMA_CONTEXT_WINDOW, 'num_gpu': num_gpu_val}
    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Requesting page order analysis (Attempt {attempt + 1})...")
            response = ollama_client.chat(model=OLLAMA_MODEL, messages=messages, format='json', options=options)
            response_content = response['message']['content']
            logging.debug(f"Raw Ollama ordering response content:\n---\n{response_content}\n---")
            page_order_data = json.loads(response_content).get("page_order")
            if page_order_data and isinstance(page_order_data, list):
                clean_order: list[int] = []
                for item in page_order_data:
                    if isinstance(item, int):
                        clean_order.append(item)
                    elif isinstance(item, str):
                        match = re.search(r'\d+', item)
                        if match:
                            clean_order.append(int(match.group(0)))
                return clean_order
            logging.warning("AI response for page order was empty or not a list.")
        except json.JSONDecodeError:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Failed to decode JSON from Ollama's ordering response.")
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{MAX_RETRIES}: Page ordering analysis failed: {e}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY_SECONDS)
    logging.error("All retry attempts for page ordering failed. Falling back to the original page order.")
    return original_page_numbers

def get_text_for_page(full_text: str, page_number: int) -> str:
    pattern = re.compile(r'--- Page ' + str(page_number) + r' ---\n(.*?)(?=\n--- Page|\Z)', re.DOTALL)
    match = pattern.search(full_text)
    return match.group(1).strip() if match else ""

# --- PDF Processing Functions ---
def merge_pdfs(pdf_list: list[str], output_path: str) -> str | None:
    logging.info(f"Merging {len(pdf_list)} PDF files into '{os.path.basename(output_path)}'...")
    result_pdf = fitz.open()
    try:
        for pdf_path in pdf_list:
            try:
                with fitz.open(pdf_path) as pdf_doc:
                    result_pdf.insert_pdf(pdf_doc)
                logging.debug(f"Successfully appended '{os.path.basename(pdf_path)}' to the merge batch.")
            except Exception as e:
                logging.error(f"Could not process '{pdf_path}' during merge and will be skipped. Error: {e}")
        result_pdf.save(output_path)
        return output_path
    except Exception as e:
        logging.error(f"A critical error occurred during the PDF merge operation: {e}")
        return None
    finally:
        result_pdf.close()

def perform_ocr_on_pdf(file_path: str) -> tuple[str, int]:
    page_count = 0
    full_extracted_text = ""
    doc: fitz.Document | None = None
    try:
        doc = fitz.open(file_path)
        page_count = doc.page_count
        logging.info(f"Starting OCR for '{os.path.basename(file_path)}' which has {page_count} pages.")
        for i, page in enumerate(doc): # type: ignore
            page_number = i + 1
            full_extracted_text += PAGE_MARKER_TEMPLATE.format(page_number)
            current_page_text = page.get_text().strip() # type: ignore
            if not current_page_text:
                logging.info(f"Page {page_number} contains no selectable text. Performing image-based OCR.")
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # type: ignore
                img = Image.open(io.BytesIO(pix.tobytes("png"))) # type: ignore
                try:
                    osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT)
                    rotation = osd.get('rotate', 0)
                    if rotation > 0:
                        logging.info(f"Page {page_number} appears to be rotated by {rotation} degrees. Correcting orientation.")
                        img = img.rotate(-rotation, expand=True)
                except Exception as e:
                    logging.warning(f"Could not perform orientation detection on page {page_number}. Error: {e}")
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_bytes = img_byte_arr.getvalue()
                results = ocr_reader.readtext(img_bytes, detail=0, paragraph=True)
                current_page_text = "\n".join(map(str, results))
                logging.info(f"Successfully extracted text from image on page {page_number}.")
            full_extracted_text += current_page_text
        return full_extracted_text, page_count
    except Exception as e:
        logging.error(f"A critical error occurred during OCR on '{file_path}': {e}")
        return "", page_count
    finally:
        if doc:
            doc.close()

def create_output_files(source_pdf_path: str, sub_category: str, title: str, parent_category_path: str):
    file_name = os.path.basename(source_pdf_path)
    logging.info(f"Creating final output files for '{file_name}' -> Sub-Category: {sub_category}, Title: '{title}'")
    text_for_report, ocr_doc_obj = "", None
    doc: fitz.Document | None = None
    reason = "Success"
    try:
        doc = fitz.open(source_pdf_path)
        ocr_doc_obj = fitz.open()
        for page in doc: # type: ignore
            page_text = page.get_text().strip() # type: ignore
            if not page_text:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # type: ignore
                img = Image.open(io.BytesIO(pix.tobytes("png"))) # type: ignore
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
            new_page = ocr_doc_obj.new_page(width=page.rect.width, height=page.rect.height) # type: ignore
            pix = page.get_pixmap() # type: ignore
            new_page.insert_image(new_page.rect, stream=io.BytesIO(pix.tobytes("png"))) # type: ignore
            new_page.insert_text(page.rect.tl, page_text, render_mode=3)
        logging.info(f"Successfully created searchable text layer for '{file_name}'.")
    except Exception as e:
        logging.error(f"Error during final OCR pass for '{file_name}': {e}")
        reason = f"Final OCR pass failed due to: {e}"
    finally:
        if doc: doc.close()
    sanitized_sub_category = "".join(c for c in sub_category if c.isalnum() or c in (' ', '-', '_')).rstrip().replace(' ', '_')
    sanitized_title = "".join(c for c in title if c.isalnum() or c in (' ', '.', '-', '_', '(', ')')).rstrip().replace(' ', '_')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_name_base = f"{sanitized_sub_category}_{sanitized_title}_{timestamp}"
    destination_dir = parent_category_path
    os.makedirs(destination_dir, exist_ok=True)
    original_copy_path = os.path.join(destination_dir, f"{new_name_base}.pdf")
    ocr_copy_path = os.path.join(destination_dir, f"{new_name_base}_ocr.pdf")
    markdown_path = os.path.join(destination_dir, f"{new_name_base}.md")
    try:
        if DRY_RUN:
            logging.info(f"[DRY RUN] Would create files for {file_name} in '{destination_dir}'")
        else:
            shutil.copy2(source_pdf_path, original_copy_path)
            logging.info(f"Saved original copy to: {original_copy_path}")
            if ocr_doc_obj:
                ocr_doc_obj.save(ocr_copy_path, garbage=4, deflate=True)
                logging.info(f"Saved searchable OCR copy to: {ocr_copy_path}")
            markdown_content = f"""# Document Analysis Report\n\n## Source File: {file_name}\n## Assigned Category: {sub_category}\n## Assigned Title: {title}\n\n---\n\n## Extracted Text (OCR)\n\n```\n{text_for_report.strip()}\n```\n\n---\n\n## Processing Summary\n- **Status:** {reason}"""
            with open(markdown_path, "w", encoding="utf-8") as md_file:
                md_file.write(markdown_content)
            logging.info(f"Saved Markdown report to: {markdown_path}")
    except Exception as e:
        logging.error(f"Error saving final files for '{file_name}': {e}")
    finally:
        if ocr_doc_obj:
            ocr_doc_obj.close()

def split_and_process_pdf(original_pdf_path: str, final_documents: list[dict]) -> list[str]:
    temp_files_to_clean = []
    original_doc: fitz.Document | None = None
    try:
        original_doc = fitz.open(original_pdf_path)
        for i, doc_details in enumerate(final_documents):
            pages_to_include = doc_details.get('page_order', [])
            category = doc_details.get('category')
            sub_category = doc_details.get('sub_category')
            title = doc_details.get('title')
            if not pages_to_include or not category or not sub_category or not title:
                logging.warning(f"Skipping incomplete document group #{i+1} due to missing data: {doc_details}")
                continue
            logging.info(f"Processing document group #{i+1}: Category='{category}', Title='{title}', Pages={pages_to_include}")
            new_doc = fitz.open()
            zero_indexed_pages = [p - 1 for p in pages_to_include]
            for page_num in zero_indexed_pages:
                if 0 <= page_num < original_doc.page_count:
                    new_doc.insert_pdf(original_doc, from_page=page_num, to_page=page_num)
            temp_pdf_path = os.path.join(os.path.dirname(original_pdf_path), f"temp_split_{i}_{os.path.basename(original_pdf_path)}")
            new_doc.save(temp_pdf_path)
            new_doc.close()
            temp_files_to_clean.append(temp_pdf_path)
            parent_category_path = ABSOLUTE_CATEGORIES.get(category, ABSOLUTE_CATEGORIES["other"])
            create_output_files(temp_pdf_path, sub_category, title, parent_category_path)
        return temp_files_to_clean
    except Exception as e:
        logging.error(f"Error during splitting and processing for {original_pdf_path}: {e}")
        return temp_files_to_clean
    finally:
        if original_doc:
            original_doc.close()

# --- Main Logic ---
def main():
    logging.info("\n" + "="*60 + "\n========== STARTING NEW DOCUMENT PROCESSING RUN ==========\n" + "="*60)
    cleanup_archive(ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS)

    logging.info("--- STAGE 1 of 5: Preparing Batch File ---")
    try:
        initial_files = [os.path.join(INTAKE_DIR, f) for f in os.listdir(INTAKE_DIR) if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(INTAKE_DIR, f))]
    except FileNotFoundError:
        logging.critical(f"The intake directory '{INTAKE_DIR}' does not exist. Halting.")
        return
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

    all_input_pages = set()
    try:
        with fitz.open(file_to_process) as doc:
            all_input_pages = set(range(1, doc.page_count + 1))
        logging.info(f"Initialized safety net: Found {len(all_input_pages)} total pages in the input batch.")
    except Exception as e:
        logging.critical(f"Could not open and count pages in '{file_name}'. Halting. Error: {e}")
        return

    processed_successfully = False
    temp_split_paths: list[str] = []
    try:
        logging.info("--- STAGE 2 of 5: Performing Initial OCR on Batch ---")
        full_pdf_text, page_count = perform_ocr_on_pdf(file_to_process)
        if not full_pdf_text:
            raise ValueError("Initial OCR failed to extract any text.")
        logging.info("--- STAGE 2 COMPLETE ---")

        logging.info("--- STAGE 3 of 5: Classifying Individual Pages ---")
        recent_categories: list[str] = []
        page_classifications = []
        for i in range(1, page_count + 1):
            page_text = get_text_for_page(full_pdf_text, i)
            if not page_text.strip():
                logging.warning(f"Page {i} has no text content. Assigning to 'other' category.")
                page_classifications.append({'page_num': i, 'category': 'other'})
                continue

            logging.info(f"Classifying page {i}/{page_count} (Context: {recent_categories})...")
            category = classify_single_page(page_text, recent_categories)
            page_classifications.append({'page_num': i, 'category': category})
            logging.info(f"Page {i} classified as: '{category}'")

            if category not in recent_categories and category != 'other':
                recent_categories.append(category)

        logging.info("--- STAGE 3 COMPLETE ---")
        logging.debug(f"Full classification results: {page_classifications}")

        logging.info("--- STAGE 4 of 5: Grouping, Titling, and Ordering Documents ---")
        if not page_classifications:
            raise ValueError("No pages were classified. Cannot form document groups.")

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

        logging.info(f"Identified {len(document_groups)} logical document(s) based on classification blocks.")

        final_documents = []
        for group in document_groups:
            pages = group['pages']
            category = group['category']

            group_text_blob = "".join(PAGE_MARKER_TEMPLATE.format(page_num) + get_text_for_page(full_pdf_text, page_num) for page_num in pages)

            sub_category, title = generate_title_and_subcategory(group_text_blob, category)
            page_order = get_correct_page_order(group_text_blob, pages)

            final_documents.append({
                'category': category,
                'sub_category': sub_category,
                'title': title,
                'page_order': page_order
            })
        logging.info("--- STAGE 4 COMPLETE ---")

        # --- Safety Net Verification ---
        all_processed_pages = set()
        for doc in final_documents:
            order_list = doc.get('page_order')
            if isinstance(order_list, list):
                all_processed_pages.update(order_list)

        lost_pages = sorted(list(all_input_pages - all_processed_pages))

        if lost_pages:
            logging.critical(f"CRITICAL: {len(lost_pages)} pages were lost during processing! Pages: {lost_pages}. Creating a '_lost_and_found' document for them.")

            lost_category_name = "_lost_and_found"
            if lost_category_name not in ABSOLUTE_CATEGORIES:
                lost_path = os.path.join(PROCESSED_DIR, lost_category_name)
                os.makedirs(lost_path, exist_ok=True)
                ABSOLUTE_CATEGORIES[lost_category_name] = lost_path

            final_documents.append({
                'category': 'other',
                'sub_category': lost_category_name,
                'title': f"Lost_Pages_from_{os.path.splitext(file_name)[0]}",
                'page_order': lost_pages
            })
            logging.info(f"Added '_lost_and_found' document group with pages: {lost_pages}")
        else:
            logging.info("Safety net check passed: All input pages are accounted for.")
        # --- End Safety Net Verification ---

        logging.info("--- STAGE 5 of 5: Splitting and Creating Final Files ---")
        temp_split_paths = split_and_process_pdf(file_to_process, final_documents)
        logging.info("--- STAGE 5 COMPLETE ---")

        processed_successfully = True

    except Exception as e:
        logging.critical(f"A critical, unhandled error occurred during processing of '{file_name}': {e}", exc_info=True)
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
                            shutil.move(original_file, os.path.join(ARCHIVE_DIR, os.path.basename(original_file)))
                            logging.info(f"Archived original file: {os.path.basename(original_file)}")
                        except Exception as e:
                            logging.error(f"Failed to archive original file '{os.path.basename(original_file)}': {e}")
        else:
            logging.warning(f"Processing for '{file_name}' was not successful. Original files will remain in '{INTAKE_DIR}'.")

        if temp_merged_path and os.path.exists(temp_merged_path):
            try:
                os.remove(temp_merged_path)
                logging.info(f"Removed temporary merged file: {os.path.basename(temp_merged_path)}")
            except Exception as e:
                logging.error(f"Failed to remove temporary merged file: {e}")

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

if __name__ == "__main__":
    main()

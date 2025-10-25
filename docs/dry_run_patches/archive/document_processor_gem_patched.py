"""Dry-run patched copy of Document_Scanner_Ollama_outdated/document_processor_gem.py
Redirects repo-local outputs to TEST_TMPDIR-safe locations when possible.
"""
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

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        import tempfile
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

warnings.filterwarnings(
    "ignore",
    message=".*'pin_memory' argument is set as true but no accelerator is found.*"
)

# Minimal fallbacks
DRY_RUN = os.environ.get('DRY_RUN', 'true').lower() in ('1', 'true', 'yes')
INTAKE_DIR = os.environ.get('INTAKE_DIR', os.path.join(select_tmp_dir(), 'intake'))
PROCESSED_DIR = os.environ.get('PROCESSED_DIR', os.path.join(select_tmp_dir(), 'processed'))
ARCHIVE_DIR = os.environ.get('ARCHIVE_DIR', os.path.join(select_tmp_dir(), 'archive'))
LOG_FILE = os.environ.get('LOG_FILE', os.path.join(select_tmp_dir(), 'document_processor_gem.log'))
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '3'))
RETRY_DELAY_SECONDS = int(os.environ.get('RETRY_DELAY_SECONDS', '2'))
ARCHIVE_RETENTION_DAYS = int(os.environ.get('ARCHIVE_RETENTION_DAYS', '30'))
try:
    CATEGORIES = json.loads(os.environ.get('CATEGORIES_JSON', '{}') or '{}') or {'other': ''}
except Exception:
    CATEGORIES = {'other': ''}

log_level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}
logging.basicConfig(level=log_level_map.get(LOG_LEVEL.upper(), logging.INFO), format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler(LOG_FILE) if LOG_FILE else logging.NullHandler(), logging.StreamHandler()])

model_cache_dir = os.path.join(select_tmp_dir(), 'model_cache')
os.makedirs(model_cache_dir, exist_ok=True)
try:
    import ollama
    import easyocr
    import pytesseract
    ocr_reader = easyocr.Reader(['en'], model_storage_directory=model_cache_dir)
    ollama_client = ollama.Client(host=os.environ.get('OLLAMA_HOST', 'http://localhost:11434'))
except Exception as e:
    logging.warning(f"External LLM/OCR init failed in dry-run patched copy: {e}")

ABSOLUTE_CATEGORIES = {category_name: os.path.join(PROCESSED_DIR, relative_path) for category_name, relative_path in CATEGORIES.items()}
for category_path in ABSOLUTE_CATEGORIES.values():
    os.makedirs(category_path, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

PAGE_MARKER_TEMPLATE = "\n\n--- Page {} ---\n\n"

def cleanup_archive(directory: str, retention_days: int):
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
                except Exception as e:
                    logging.error(f"Error processing archive file '{file_path}' for cleanup: {e}")
    except Exception as e:
        logging.error(f"Failed to list files in archive directory '{directory}': {e}")

def merge_pdfs(pdf_list: list[str], output_path: str) -> str | None:
    result_pdf = fitz.open()
    try:
        for pdf_path in pdf_list:
            try:
                with fitz.open(pdf_path) as pdf_doc:
                    result_pdf.insert_pdf(pdf_doc)
            except Exception as e:
                logging.error(f"Could not process '{pdf_path}' during merge: {e}")
        os.makedirs(os.path.dirname(output_path) or select_tmp_dir(), exist_ok=True)
        result_pdf.save(output_path)
        return output_path
    except Exception as e:
        logging.error(f"Merge failed: {e}")
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
        for i, page in enumerate(doc):
            page_number = i + 1
            full_extracted_text += PAGE_MARKER_TEMPLATE.format(page_number)
            current_page_text = page.get_text().strip()
            if not current_page_text:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                try:
                    osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT)
                    rotation = osd.get('rotate', 0)
                    if rotation > 0:
                        img = img.rotate(-rotation, expand=True)
                except Exception:
                    pass
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_bytes = img_byte_arr.getvalue()
                try:
                    results = ocr_reader.readtext(img_bytes, detail=0, paragraph=True)
                    current_page_text = "\n".join(map(str, results))
                except Exception:
                    current_page_text = ""
            full_extracted_text += current_page_text
        return full_extracted_text, page_count
    except Exception as e:
        logging.error(f"OCR failed for '{file_path}': {e}")
        return "", page_count
    finally:
        if doc:
            doc.close()

def create_output_files(source_pdf_path: str, sub_category: str, title: str, parent_category_path: str):
    file_name = os.path.basename(source_pdf_path)
    text_for_report = ""
    ocr_doc_obj = None
    doc: fitz.Document | None = None
    reason = "Success"
    try:
        doc = fitz.open(source_pdf_path)
        ocr_doc_obj = fitz.open()
        for page in doc:
            page_text = page.get_text().strip()
            if not page_text:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                try:
                    osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT)
                    rotation = osd.get('rotate', 0)
                    if rotation > 0:
                        img = img.rotate(-rotation, expand=True)
                except Exception:
                    pass
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_bytes = img_byte_arr.getvalue()
                try:
                    results = ocr_reader.readtext(img_bytes, detail=0, paragraph=True)
                    page_text = "\n".join(map(str, results))
                except Exception:
                    page_text = ""
            text_for_report += page_text + "\n\n"
            new_page = ocr_doc_obj.new_page(width=page.rect.width, height=page.rect.height)
            pix = page.get_pixmap()
            new_page.insert_image(new_page.rect, stream=io.BytesIO(pix.tobytes("png")))
            new_page.insert_text(page.rect.tl, page_text, render_mode=3)
    except Exception as e:
        logging.error(f"Final OCR pass failed for '{file_name}': {e}")
        reason = f"Final OCR pass failed due to: {e}"
    finally:
        if doc:
            doc.close()
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
            if ocr_doc_obj:
                ocr_doc_obj.save(ocr_copy_path, garbage=4, deflate=True)
            markdown_content = f"""# Document Analysis Report\n\n## Source File: {file_name}\n## Assigned Category: {sub_category}\n## Assigned Title: {title}\n\n---\n\n## Extracted Text (OCR)\n\n```
{text_for_report.strip()}
```
\n---\n\n## Processing Summary\n- **Status:** {reason}"""
            with open(markdown_path, "w", encoding="utf-8") as md_file:
                md_file.write(markdown_content)
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
            new_doc = fitz.open()
            zero_indexed_pages = [p - 1 for p in pages_to_include]
            for page_num in zero_indexed_pages:
                if 0 <= page_num < original_doc.page_count:
                    new_doc.insert_pdf(original_doc, from_page=page_num, to_page=page_num)
            temp_pdf_path = os.path.join(os.path.dirname(original_pdf_path) or select_tmp_dir(), f"temp_split_{i}_{os.path.basename(original_pdf_path)}")
            os.makedirs(os.path.dirname(temp_pdf_path) or select_tmp_dir(), exist_ok=True)
            new_doc.save(temp_pdf_path)
            new_doc.close()
            temp_files_to_clean.append(temp_pdf_path)
            parent_category_path = ABSOLUTE_CATEGORIES.get(category, ABSOLUTE_CATEGORIES.get("other", os.path.join(PROCESSED_DIR, 'other')))
            create_output_files(temp_pdf_path, sub_category, title, parent_category_path)
        return temp_files_to_clean
    except Exception as e:
        logging.error(f"Error during splitting and processing for {original_pdf_path}: {e}")
        return temp_files_to_clean
    finally:
        if original_doc:
            original_doc.close()

def main():
    cleanup_archive(ARCHIVE_DIR, ARCHIVE_RETENTION_DAYS)
    try:
        initial_files = [os.path.join(INTAKE_DIR, f) for f in os.listdir(INTAKE_DIR) if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(INTAKE_DIR, f))]
    except FileNotFoundError:
        logging.critical(f"The intake directory '{INTAKE_DIR}' does not exist. Halting.")
        return
    if not initial_files:
        logging.info("No new PDF files found.")
        return
    file_to_process = None
    temp_merged_path = None
    if len(initial_files) > 1:
        temp_merged_name = f"temp_mega_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        temp_merged_path = os.path.join(INTAKE_DIR, temp_merged_name)
        file_to_process = merge_pdfs(initial_files, temp_merged_path)
    elif len(initial_files) == 1:
        file_to_process = initial_files[0]
    if not file_to_process:
        logging.error("Failed to prepare a file for processing.")
        return
    file_name = os.path.basename(file_to_process)
    all_input_pages = set()
    try:
        with fitz.open(file_to_process) as doc:
            all_input_pages = set(range(1, doc.page_count + 1))
    except Exception as e:
        logging.critical(f"Could not open and count pages in '{file_name}'. Halting. Error: {e}")
        return
    processed_successfully = False
    temp_split_paths: list[str] = []
    try:
        full_pdf_text, page_count = perform_ocr_on_pdf(file_to_process)
        if not full_pdf_text:
            raise ValueError("Initial OCR failed to extract any text.")
        recent_categories: list[str] = []
        page_classifications = []
        for i in range(1, page_count + 1):
            page_text = get_text_for_page(full_pdf_text, i)
            if not page_text.strip():
                page_classifications.append({'page_num': i, 'category': 'other'})
                continue
            category = 'other'
            page_classifications.append({'page_num': i, 'category': category})
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
        final_documents = []
        for group in document_groups:
            pages = group['pages']
            category = group['category']
            group_text_blob = ''.join(PAGE_MARKER_TEMPLATE.format(page_num) + get_text_for_page(full_pdf_text, page_num) for page_num in pages)
            sub_category = 'default'
            title = f"doc_{pages[0]}_{pages[-1]}"
            page_order = pages
            final_documents.append({'category': category, 'sub_category': sub_category, 'title': title, 'page_order': page_order})
        temp_split_paths = split_and_process_pdf(file_to_process, final_documents)
        processed_successfully = True
    except Exception as e:
        logging.critical(f"A critical, unhandled error occurred during processing of '{file_name}': {e}", exc_info=True)
    finally:
        if processed_successfully:
            for original_file in initial_files:
                if os.path.exists(original_file):
                    if DRY_RUN:
                        logging.info(f"[DRY RUN] Would archive original file: {os.path.basename(original_file)}")
                    else:
                        try:
                            shutil.move(original_file, os.path.join(ARCHIVE_DIR, os.path.basename(original_file)))
                        except Exception as e:
                            logging.error(f"Failed to archive original file '{os.path.basename(original_file)}': {e}")
        if temp_merged_path and os.path.exists(temp_merged_path):
            try:
                os.remove(temp_merged_path)
            except Exception:
                pass
        if temp_split_paths:
            for temp_path in temp_split_paths:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

if __name__ == '__main__':
    main()
# Dry-run patched copy of Document_Scanner_Ollama_outdated/document_processor_gem.py
# Purpose: map destination_dir to a test-safe base when possible.

import os
import tempfile
try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()

# Example of replacing the write block inside create_output_files

def create_output_files_safe_example(destination_dir, source_pdf_path, md_content):
    # Preserve explicit env override
    env_dest = os.environ.get('ARCHIVE_DIR')
    safe_base = env_dest or select_tmp_dir()
    mapped_dest = os.path.join(safe_base, os.path.basename(destination_dir)) if safe_base else destination_dir
    try:
        os.makedirs(mapped_dest, exist_ok=True)
    except Exception:
        mapped_dest = destination_dir
        os.makedirs(mapped_dest, exist_ok=True)

    original_copy_path = os.path.join(mapped_dest, os.path.basename(source_pdf_path))
    try:
        shutil.copy2(source_pdf_path, original_copy_path)
    except Exception as e:
        # fallback to original destination if needed
        fallback_path = os.path.join(destination_dir, os.path.basename(source_pdf_path))
        shutil.copy2(source_pdf_path, fallback_path)

    # Write markdown to mapped_dest
    md_path = os.path.join(mapped_dest, 'report.md')
    with open(md_path, 'w', encoding='utf-8') as md_file:
        md_file.write(md_content)

import os
import sqlite3
import shutil
import re
import warnings
from datetime import datetime
import logging
from typing import List, Optional, Dict, Any, Union

import requests
import numpy as np
from dotenv import load_dotenv
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import easyocr
import fitz  # PyMuPDF

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

# --- INITIAL SETUP ---
load_dotenv()
warnings.filterwarnings("ignore", message=".*'pin_memory' argument is set as true.*")

# --- Status Constants ---
STATUS_PENDING_VERIFICATION = "pending_verification"
STATUS_FAILED = "failed"

# --- EasyOCR Singleton ---
class EasyOCRSingleton:
    _reader = None

    @classmethod
    def get_reader(cls):
        if cls._reader is None:
            logging.info("Initializing EasyOCR Reader (this may take a moment)...")
            cls._reader = easyocr.Reader(["en"], gpu=False)
            logging.info("EasyOCR Reader initialized.")
        return cls._reader

BROAD_CATEGORIES = [
    "Financial Document",
    "Legal Document",
    "Personal Correspondence",
    "Technical Document",
    "Medical Record",
    "Educational Material",
    "Receipt or Invoice",
    "Form or Application",
    "News Article or Publication",
    "Other",
]

def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to safe base for output."""
    sanitized = "".join([c for c in os.path.splitext(filename)[0] if c.isalnum() or c in ("-", "_")]).rstrip()
    if not sanitized:
        sanitized = "document"
    return sanitized

def _sanitize_category(category: str) -> str:
    """Sanitize category for directory names."""
    cat = "".join(c for c in category if c.isalnum() or c in (' ', '-', '_')).rstrip().replace(' ', '_')
    return cat if cat else "Other"

def _process_single_page_from_file(
    cursor: sqlite3.Cursor,
    image_path: str,
    batch_id: int,
    source_filename: str,
    page_num: int,
) -> bool:
    try:
        logging.info(
            f"  - Processing Page {page_num} from file: {os.path.basename(image_path)}"
        )
        skip_ocr = os.getenv("DEBUG_SKIP_OCR", "False").lower() in ("true", "1", "t")
        if skip_ocr:
            logging.info("    - DEBUG_SKIP_OCR is True. Skipping OCR and rotation.")
            ocr_text = f"OCR SKIPPED FOR DEBUG - Page {page_num} of {source_filename}"
            rotation = 0
        else:
            # Image existence and size check
            if not os.path.exists(image_path):
                logging.error(f"    - Image file {os.path.basename(image_path)} is missing before opening.")
                return False
            file_size = os.path.getsize(image_path)
            if file_size == 0:
                logging.error(f"    - Image file {os.path.basename(image_path)} is empty before opening.")
                return False
            logging.debug(f"    - DEBUG: Attempting to open {os.path.basename(image_path)} (size: {file_size} bytes).")
            image = Image.open(image_path)
            try:
                osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
                rotation = osd.get("rotate", 0)
            finally:
                image.close()
            # Re-open for rotation if needed
            if rotation and rotation > 0:
                logging.info(f"    - Rotating page by {rotation} degrees.")
                image = Image.open(image_path)
                image = image.rotate(rotation, expand=True)
                image.save(image_path, "PNG")
                image.close()
            image = Image.open(image_path)
            reader = EasyOCRSingleton.get_reader()
            ocr_results = reader.readtext(np.array(image))
            image.close()
            ocr_text = " ".join([text for _, text, _ in ocr_results])
        cursor.execute(
            "INSERT INTO pages (batch_id, source_filename, page_number, processed_image_path, ocr_text, status, rotation_angle) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                batch_id,
                source_filename,
                page_num,
                image_path,
                ocr_text,
                STATUS_PENDING_VERIFICATION,
                rotation,
            ),
        )
        return True
    except Exception as e:
        logging.error(
            f"    - Failed to process Page {page_num} from file {os.path.basename(image_path)}: {e}"
        )
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as del_e:
                logging.error(f"    - Failed to delete orphaned image: {del_e}")
        return False

def get_ai_classification(page_text: str, seen_categories: List[str]) -> str:
    ollama_host = os.getenv("OLLAMA_HOST")
    ollama_model = os.getenv("OLLAMA_MODEL")
    prompt = f"""
    Analyze the following text from a scanned document page. Based on the text, which of the following categories best describes it?
    Available Categories: {', '.join(BROAD_CATEGORIES)}
    Respond with ONLY the single best category name from the list.
    DO NOT provide any explanation, preamble, or summary. Your entire response must be only one of the category names listed above.
    ---
    TEXT TO ANALYZE:
    {page_text[:4000]}
    ---
    """
    try:
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        response_json = response.json()
        category = response_json.get("response", "Other").strip().strip('"`')
        if category not in BROAD_CATEGORIES:
            logging.warning(
                f"  [AI WARNING] Model returned invalid category: '{category}'. Defaulting to 'Other'."
            )
            return "Other"
        return category
    except requests.exceptions.RequestException as e:
        logging.error(f"  [AI ERROR] Could not connect to Ollama: {e}")
        return "AI_Error"

def process_batch() -> bool:
    logging.info("--- Starting New Batch ---")
    db_path = os.getenv("DATABASE_PATH")
    conn = None
    batch_id = -1
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"INSERT INTO batches (status) VALUES ('{STATUS_PENDING_VERIFICATION}')")
        batch_id = cursor.lastrowid
        conn.commit()
        logging.info(f"Created new batch with ID: {batch_id}")

        intake_dir = os.getenv("INTAKE_DIR")
        processed_dir = os.getenv("PROCESSED_DIR")
        archive_dir = os.getenv("ARCHIVE_DIR")
        if intake_dir is None:
            logging.error("INTAKE_DIR environment variable is not set.")
            return False
        if archive_dir is None:
            logging.error("ARCHIVE_DIR environment variable is not set.")
            return False
        os.makedirs(archive_dir, exist_ok=True)
        batch_image_dir = os.path.join(processed_dir, str(batch_id))
        os.makedirs(batch_image_dir, exist_ok=True)

        pdf_files = [f for f in os.listdir(intake_dir) if f.lower().endswith(".pdf")]
        for filename in pdf_files:
            source_pdf_path = os.path.join(intake_dir, filename)
            logging.info(f"\nProcessing file: {filename}")
            sanitized_filename = _sanitize_filename(filename)
            images = convert_from_path(
                source_pdf_path,
                dpi=300,
                output_folder=batch_image_dir,
                fmt="png",
                output_file=f"{sanitized_filename}_page",
                thread_count=4,
            )
            image_files = sorted([img.filename for img in images])
            for i, image_path in enumerate(image_files):
                _process_single_page_from_file(
                    cursor, image_path, batch_id, filename, i + 1
                )
            conn.commit()
            logging.info(f"  - Successfully processed and saved {len(images)} pages.")
            try:
                shutil.move(source_pdf_path, os.path.join(archive_dir, filename))
                logging.info("  - Archived original file.")
            except Exception as move_e:
                logging.error(f"  - Failed to archive original file: {move_e}")

        logging.info("\n--- Starting AI 'First Guess' Classification ---")
        cursor.execute("SELECT id, ocr_text FROM pages WHERE batch_id = ?", (batch_id,))
        pages_to_classify = cursor.fetchall()
        for page_id, ocr_text in pages_to_classify:
            logging.info(f"  - Classifying Page ID: {page_id}")
            ai_category = get_ai_classification(ocr_text, [])
            cursor.execute(
                "UPDATE pages SET ai_suggested_category = ? WHERE id = ?",
                (ai_category, page_id),
            )
        conn.commit()

        logging.info("\n--- Batch Processing Complete ---")
        return True
    except Exception as e:
        logging.critical(f"[CRITICAL ERROR] An error occurred during batch processing: {e}")
        if conn and batch_id != -1:
            try:
                cursor.execute(
                    f"UPDATE batches SET status = '{STATUS_FAILED}' WHERE id = ?", (batch_id,)
                )
                conn.commit()
            except Exception as update_e:
                logging.error(f"Failed to update batch status to failed: {update_e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def rerun_ocr_on_page(page_id: int, rotation_angle: int) -> bool:
    logging.info(f"--- Re-running OCR for Page ID: {page_id} with rotation {rotation_angle} ---")
    db_path = os.getenv("DATABASE_PATH")
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        result = cursor.execute(
            "SELECT processed_image_path FROM pages WHERE id = ?", (page_id,)
        ).fetchone()
        if not result:
            logging.error(f"  - No page found with ID {page_id}")
            return False
        image_path = result["processed_image_path"]
        if not os.path.exists(image_path):
            logging.error(f"  - Image file not found at {image_path}")
            return False

        image = Image.open(image_path)
        # PIL rotates counter-clockwise. If UI expects clockwise, negative angle is used.
        rotated_image = image.rotate(-rotation_angle, expand=True)
        rotated_image.save(image_path, "PNG")
        image.close()
        logging.info(f"  - Physically rotated and saved image at {image_path}")

        reader = EasyOCRSingleton.get_reader()
        ocr_results = reader.readtext(np.array(rotated_image))
        rotated_image.close()
        new_ocr_text = " ".join([text for _, text, _ in ocr_results])

        cursor.execute(
            "UPDATE pages SET ocr_text = ?, rotation_angle = ? WHERE id = ?",
            (new_ocr_text, rotation_angle, page_id),
        )
        conn.commit()
        logging.info("--- OCR Re-run Complete ---")
        return True
    except Exception as e:
        logging.critical(f"[CRITICAL ERROR] An error occurred during OCR re-run: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def _get_page_number_from_ai(page_text: str) -> Optional[int]:
    prompt = f"""
    Analyze the following text from a single page.
    What is the printed page number?
    Your response MUST be an integer (e.g., "1", "2", "3") or the word "none" if no page number is found.
    Do not provide any other text or explanation.

    --- PAGE TEXT ---
    {page_text[:3000]}
    --- END PAGE TEXT ---
    """
    ollama_host = os.getenv("OLLAMA_HOST")
    ollama_model = os.getenv("OLLAMA_MODEL")
    try:
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=30,
        )
        response.raise_for_status()
        result = response.json().get("response", "none").strip().lower()
        match = re.search(r"\d+", result)
        if match:
            return int(match.group(0))
        return None
    except (requests.exceptions.RequestException, ValueError) as e:
        logging.error(f"[AI SUB-TASK ERROR] Could not get page number: {e}")
        return None

def get_ai_suggested_order(pages: List[Union[Dict, Any]]) -> List[int]:
    logging.info(f"--- Starting 'Extract, then Sort' for {len(pages)} pages ---")
    numbered_pages = []
    unnumbered_pages = []
    for page in pages:
        page_id = page["id"]
        page_text = page["ocr_text"]
        logging.info(f"  - Extracting page number from Page ID: {page_id}...")
        extracted_num = _get_page_number_from_ai(page_text)
        if extracted_num is not None:
            logging.info(f"    - AI found page number: {extracted_num}")
            numbered_pages.append({"id": page_id, "num": extracted_num})
        else:
            logging.info("    - AI found no page number.")
            unnumbered_pages.append({"id": page_id})

    numbered_pages.sort(key=lambda p: p["num"])
    sorted_numbered_ids = [p["id"] for p in numbered_pages]
    logging.info(f"\n  - Sorted numbered pages: {sorted_numbered_ids}")

    unnumbered_ids = [p["id"] for p in unnumbered_pages]
    logging.info(f"  - Unnumbered pages (will be appended): {unnumbered_ids}")

    final_order = sorted_numbered_ids + unnumbered_ids
    logging.info(f"--- 'Extract, then Sort' complete. Final order: {final_order} ---")
    return final_order

def get_ai_suggested_filename(document_text: str, category: str) -> str:
    ollama_host = os.getenv("OLLAMA_HOST")
    ollama_model = os.getenv("OLLAMA_MODEL")
    prompt = f"""
You are a file naming expert. Your ONLY task is to create a filename-safe title from the document text provided.

RULES:
- The title MUST be 4-6 words long.
- Use hyphens (-) instead of spaces.
- DO NOT include file extensions.
- DO NOT include the date.
- DO NOT add ANY introductory text, explanation, or any words other than the title itself.

GOOD EXAMPLE: Brian-McCaleb-Tire-Service-Invoice
BAD EXAMPLE: Based on the text, a good title would be: Brian-McCaleb-Tire-Service-Invoice

Your ENTIRE response MUST be ONLY the filename title.

--- DOCUMENT TEXT (Category: '{category}') ---
{document_text[:6000]}
--- END DOCUMENT TEXT ---
    """
    try:
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=90,
        )
        response.raise_for_status()
        ai_title = response.json().get("response", "Untitled-Document").strip()
        ai_title = re.sub(r'^\s*Here.+?:?\s*', '', ai_title, flags=re.IGNORECASE)
        sanitized_title = re.sub(r'[^\w\-_]', '', ai_title).strip('-')
        if not sanitized_title:
            sanitized_title = "Untitled-Document"
        current_date = datetime.now().strftime("%Y-%m-%d")
        return f"{current_date}_{sanitized_title}"

    except requests.exceptions.RequestException as e:
        logging.error(f"[AI FILENAME ERROR] Could not generate filename: {e}")
        current_date = datetime.now().strftime("%Y-%m-%d")
        return f"{current_date}_AI-Error-Generating-Name"

def export_document(pages: List[Union[Dict, Any]], final_name_base: str, category: str) -> bool:
    logging.info(f"--- EXPORTING Document: {final_name_base} ---")
    filing_cabinet_dir = os.getenv("FILING_CABINET_DIR")
    if not filing_cabinet_dir:
        logging.error("FILING_CABINET_DIR is not set in the .env file. Cannot export.")
        return False

    category_dir_name = _sanitize_category(category)
    destination_dir = os.path.join(filing_cabinet_dir, category_dir_name)
    os.makedirs(destination_dir, exist_ok=True)

    image_paths = [p["processed_image_path"] for p in pages]
    full_ocr_text = "\n\n---\n\n".join([p["ocr_text"] for p in pages])

    try:
        # 1. Standard PDF
        standard_pdf_path = os.path.join(destination_dir, f"{final_name_base}.pdf")
        images = []
        for p in image_paths:
            if os.path.exists(p):
                img = Image.open(p)
                images.append(img)
            else:
                logging.warning(f"Image not found for PDF export: {p}")
        if images:
            rgb_images = [img.convert('RGB') if img.mode != 'RGB' else img for img in images]
            if rgb_images:
                rgb_images[0].save(
                    standard_pdf_path, save_all=True, append_images=rgb_images[1:]
                )
                logging.info(f"  - Saved Standard PDF: {standard_pdf_path}")
            for img in rgb_images:
                img.close()

        # 2. Searchable PDF
        searchable_pdf_path = os.path.join(destination_dir, f"{final_name_base}_ocr.pdf")
        doc = fitz.open()
        for page_data in pages:
            img_path = page_data["processed_image_path"]
            ocr_text = page_data["ocr_text"]
            if not os.path.exists(img_path):
                logging.warning(f"Image not found for OCR PDF export: {img_path}")
                continue
            img_doc = fitz.open(img_path)
            rect = img_doc[0].rect
            pdf_page = doc.new_page(width=rect.width, height=rect.height)
            pdf_page.insert_image(rect, filename=img_path)
            pdf_page.insert_text((0, 0), ocr_text, render_mode=3)
            img_doc.close()
        if doc.page_count > 0:
            doc.save(searchable_pdf_path, garbage=4, deflate=True)
            logging.info(f"  - Saved Searchable PDF: {searchable_pdf_path}")
        doc.close()

        # 3. Markdown Log
        markdown_path = os.path.join(destination_dir, f"{final_name_base}_log.md")
        log_content = f"""# Document Export Log

- **Final Filename**: `{final_name_base}`
- **Category**: `{category}`
- **Export Timestamp**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
- **Total Pages**: {len(pages)}

## Processing Metadata

| Page ID | Source File         | Original Page # | AI Suggestion                 |
|---------|---------------------|-----------------|-------------------------------|
"""
        for p in pages:
            log_content += f"| {p['id']} | {p['source_filename']} | {p['page_number']} | {p.get('ai_suggested_category', '')} |\n"

        log_content += "\n## Full Extracted OCR Text\n\n"
        log_content += "```text\n"
        log_content += f"{full_ocr_text}\n"
        log_content += "```\n"
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(log_content)
        logging.info(f"  - Saved Markdown Log: {markdown_path}")

        return True

    except Exception as e:
        logging.error(f"[ERROR] Failed to export document {final_name_base}: {e}")
        return False

def cleanup_batch_files(batch_id: int) -> bool:
    logging.info(f"--- CLEANING UP Batch ID: {batch_id} ---")
    processed_dir = os.getenv("PROCESSED_DIR")
    if processed_dir is None:
        logging.error("PROCESSED_DIR environment variable is not set.")
        return False
    batch_image_dir = os.path.join(processed_dir, str(batch_id))
    if os.path.isdir(batch_image_dir):
        try:
            shutil.rmtree(batch_image_dir)
            logging.info(f"  - Successfully deleted temporary directory: {batch_image_dir}")
            return True
        except OSError as e:
            logging.error(f"  - Failed to delete directory {batch_image_dir}: {e}")
            return False
    else:
        logging.info(f"  - Directory not found, skipping cleanup: {batch_image_dir}")
        return True
"""
This module handles the core backend logic for the document processing pipeline.
It includes functions for:
- Converting PDF files into images.
- Running OCR (Optical Character Recognition) on images to extract text.
- Interacting with an AI model (via Ollama) for tasks like document
  classification, page number extraction, and filename suggestion.
- Managing the processing workflow via a SQLite database.
- Exporting the final, processed documents into various formats.

The main entry point for the pipeline is the `process_batch` function, which
orchestrates the initial intake and processing of new PDF files.
"""

# Standard library imports
import logging
import os
import re
import shutil
import sqlite3
import warnings
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

# Third-party imports
import fitz  # PyMuPDF
import numpy as np
import pytesseract
import requests
from pdf2image import convert_from_path
from PIL import Image

# Local application imports
import config  # Centralized configuration
from database import get_all_categories

# --- LOGGING SETUP ---
# Configures a consistent logging format for the entire module.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# --- INITIAL SETUP ---
# Suppress a common warning from the underlying torch library used by easyocr.
warnings.filterwarnings("ignore", message=".*'pin_memory' argument is set as true.*",)


# --- OCR SINGLETON ---
class EasyOCRSingleton:
    """
    Manages a single, shared instance of the easyocr.Reader.
    This prevents the time-consuming process of loading the OCR model into memory
    every time it's needed. The first call to `get_reader` will initialize it.
    """

    _reader = None

    @classmethod
    def get_reader(cls):
        """
        Returns the singleton instance of the EasyOCR reader.
        Initializes the reader on the first call.
        """
        if cls._reader is None:
            # Deferring the import of easyocr until it's actually needed can
            # speed up initial application startup time.
            import easyocr

            logging.info("Initializing EasyOCR Reader (this may take a moment)...")
            # Using gpu=False for broader compatibility. For systems with a
            # compatible NVIDIA GPU, setting this to True can significantly
            # improve OCR speed.
            cls._reader = easyocr.Reader(["en"], gpu=False)
            logging.info("EasyOCR Reader initialized.")
        return cls._reader


# --- DATABASE CONTEXT MANAGER ---
@contextmanager
def database_connection():
    """
    Provides a managed connection to the SQLite database.

    This context manager handles the opening and closing of the database connection,
    ensuring that it's always closed properly, even if errors occur. It also
    configures the connection to use `sqlite3.Row` for more readable,
    dictionary-like access to query results.

    Yields:
        sqlite3.Connection: The database connection object.
    """
    conn = None
    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        logging.critical(f"[CRITICAL DATABASE ERROR] {e}")
        # Re-raise the exception to be handled by the calling function
        raise
    finally:
        if conn:
            conn.close()


# --- AI HELPER FUNCTION ---
def _query_ollama(prompt: str, timeout: int = 60) -> Optional[str]:
    """
    Sends a prompt to the configured Ollama API endpoint and returns the response.

    This centralized function handles all communication with the AI model. It
    checks for necessary configuration, formats the request, sends it, and
    performs basic error handling.

    Args:
        prompt (str): The full prompt to send to the AI model.
        timeout (int): The timeout for the request in seconds.

    Returns:
        Optional[str]: The text content of the AI's response, or None if an
                       error occurred or the required configuration is missing.
    """
    if not config.OLLAMA_HOST or not config.OLLAMA_MODEL:
        logging.error("[AI ERROR] OLLAMA_HOST or OLLAMA_MODEL is not set.")
        return None
    try:
        response = requests.post(
            f"{config.OLLAMA_HOST}/api/generate",
            json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        return response.json().get("response", "").strip()
    except requests.exceptions.RequestException as e:
        logging.error(f"[AI ERROR] Could not connect to Ollama: {e}")
        return None


# --- FILENAME SANITIZATION ---
def _sanitize_filename(filename: str) -> str:
    """Sanitizes a string to be safe for use as a filename base."""
    # Keep only alphanumeric characters, hyphens, and underscores
    sanitized = "".join(
        [c for c in os.path.splitext(filename)[0] if c.isalnum() or c in ("-", "_")]
    ).rstrip()
    # If the sanitization results in an empty string, default to "document"
    return sanitized if sanitized else "document"


def _sanitize_category(category: str) -> str:
    """Sanitizes a category name to be safe for use as a directory name."""
    # Replace spaces with underscores for better compatibility
    cat = (
        "".join(c for c in category if c.isalnum() or c in (" ", "-", "_"))
        .rstrip()
        .replace(" ", "_")
    )
    return cat if cat else "Other"


# --- CORE PROCESSING WORKFLOW ---
def _process_single_page_from_file(
    cursor: sqlite3.Cursor,
    image_path: str,
    batch_id: int,
    source_filename: str,
    page_num: int,
) -> bool:
    """
    Processes a single image file: performs OCR and saves the result to the database.
    This function contains the logic for image rotation and text extraction.
    """
    try:
        logging.info(
            f"  - Processing Page {page_num} from file: {os.path.basename(image_path)}"
        )

        ocr_text = f"OCR SKIPPED FOR DEBUG - Page {page_num} of {source_filename}"
        rotation = 0

        if not config.DEBUG_SKIP_OCR:
            if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
                logging.error(
                    f"    - Image file {os.path.basename(image_path)} is missing or empty."
                )
                return False

            try:
                # Open the image once and perform all operations in memory
                with Image.open(image_path) as img:
                    # 1. Get orientation and determine rotation
                    try:
                        osd = pytesseract.image_to_osd(
                            img, output_type=pytesseract.Output.DICT
                        )
                        rotation = osd.get("rotate", 0)
                    except pytesseract.TesseractError as e:
                        logging.warning(f"    - Could not determine page orientation: {e}")
                        rotation = 0

                    # 2. Rotate the image object if necessary
                    if rotation and rotation > 0:
                        logging.info(f"    - Rotating page by {rotation} degrees.")
                        # The `expand=True` argument ensures the image is resized to fit the new dimensions
                        img = img.rotate(rotation, expand=True)
                        # Save the physically rotated image back to disk
                        img.save(image_path, "PNG")

                    # 3. Perform OCR on the (potentially rotated) image
                    reader = EasyOCRSingleton.get_reader()
                    # Convert PIL Image to a NumPy array, which is what easyocr expects
                    ocr_results = reader.readtext(np.array(img))
                    ocr_text = " ".join([text for _, text, _ in ocr_results])

            except IOError as e:
                logging.error(f"    - Could not open or process image {image_path}: {e}")
                return False

        # Use a parameterized query to prevent SQL injection
        cursor.execute(
            "INSERT INTO pages (batch_id, source_filename, page_number, processed_image_path, ocr_text, status, rotation_angle) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                batch_id,
                source_filename,
                page_num,
                image_path,
                ocr_text,
                config.STATUS_PENDING_VERIFICATION,
                rotation,
            ),
        )
        return True
    except Exception as e:
        logging.error(
            f"    - Failed to process Page {page_num} from file {os.path.basename(image_path)}: {e}"
        )
        # Clean up orphaned image file if an error occurs after its creation
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except OSError as del_e:
                logging.error(f"    - Failed to delete orphaned image: {del_e}")
        return False


def get_ai_classification(page_text: str) -> str:
    """
    Asks the AI model to classify a page's text into one of the predefined categories.
    """
    # Fetch the official list of categories from the database
    broad_categories = get_all_categories()
    if not broad_categories:
        logging.error("Could not fetch categories from the database. Defaulting to 'Other'.")
        return "Other"

    prompt = f"""
Analyze the following text from a scanned document page. Based on the text, which of the following categories best describes it?
Available Categories: {', '.join(broad_categories)}
Respond with ONLY the single best category name from the list.
DO NOT provide any explanation, preamble, or summary. Your entire response must be only one of the category names listed above.
---
TEXT TO ANALYZE:
{page_text[:4000]}
---
"""
    category = _query_ollama(prompt)

    if category is None:
        return "AI_Error"  # Indicates a connection or API error

    if category not in broad_categories:
        logging.warning(
            f"  [AI WARNING] Model returned invalid category: '{category}'. Defaulting to 'Other'.")
        return "Other"

    return category


def process_batch() -> bool:
    """
    The main function for processing a new batch of documents from the intake directory.
    """
    logging.info("--- Starting New Batch ---")
    batch_id = -1
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            # Create a new batch record and get its ID
            cursor.execute("INSERT INTO batches (status) VALUES (?)", (config.STATUS_PENDING_VERIFICATION,))
            batch_id = cursor.lastrowid
            conn.commit()
            logging.info(f"Created new batch with ID: {batch_id}")

            # Ensure required directories exist
            if not config.INTAKE_DIR or not config.ARCHIVE_DIR or not config.PROCESSED_DIR:
                logging.error(
                    "INTAKE_DIR, ARCHIVE_DIR, or PROCESSED_DIR environment variable is not set."
                )
                return False
            os.makedirs(config.ARCHIVE_DIR, exist_ok=True)
            batch_image_dir = os.path.join(config.PROCESSED_DIR, str(batch_id))
            os.makedirs(batch_image_dir, exist_ok=True)

            # Process each PDF file in the intake directory
            pdf_files = [
                f for f in os.listdir(config.INTAKE_DIR) if f.lower().endswith(".pdf")
            ]
            for filename in pdf_files:
                source_pdf_path = os.path.join(config.INTAKE_DIR, filename)
                logging.info(f"\nProcessing file: {filename}")
                sanitized_filename = _sanitize_filename(filename)

                # Convert PDF to a list of PNG images
                images = convert_from_path(
                    source_pdf_path,
                    dpi=300,
                    output_folder=batch_image_dir,
                    fmt="png",
                    output_file=f"{sanitized_filename}_page",
                    thread_count=4,
                )
                image_files = sorted([img.filename for img in images])

                # Process each generated image
                for i, image_path in enumerate(image_files):
                    if batch_id is not None:  # Type check for batch_id
                        _process_single_page_from_file(
                            cursor=cursor,
                            image_path=str(image_path),  # Ensure string type
                            batch_id=batch_id,
                            source_filename=filename,
                            page_num=i + 1
                        )
                conn.commit()  # Commit after each PDF is fully processed
                logging.info(
                    f"  - Successfully processed and saved {len(images)} pages."
                )

                # Move the original PDF to the archive directory
                try:
                    shutil.move(
                        source_pdf_path, os.path.join(config.ARCHIVE_DIR, filename)
                    )
                    logging.info("  - Archived original file.")
                except OSError as move_e:
                    logging.error(f"  - Failed to archive original file: {move_e}")

            # --- AI First Guess Classification ---
            logging.info("\n--- Starting AI 'First Guess' Classification ---")
            cursor.execute(
                "SELECT id, ocr_text FROM pages WHERE batch_id = ?", (batch_id,)
            )
            pages_to_classify = cursor.fetchall()
            for page in pages_to_classify:
                logging.info(f"  - Classifying Page ID: {page['id']}")
                ai_category = get_ai_classification(page["ocr_text"])
                cursor.execute(
                    "UPDATE pages SET ai_suggested_category = ? WHERE id = ?",
                    (ai_category, page["id"]),
                )
            conn.commit()

        logging.info("\n--- Batch Processing Complete ---")
        return True

    except Exception as e:
        logging.critical(
            f"[CRITICAL ERROR] An error occurred during batch processing: {e}"
        )
        # If a batch was created, mark it as failed
        if batch_id != -1:
            try:
                with database_connection() as conn:
                    conn.execute(
                        "UPDATE batches SET status = ? WHERE id = ?",
                        (config.STATUS_FAILED, batch_id),
                    )
                    conn.commit()
            except Exception as update_e:
                logging.error(
                    f"Failed to update batch status to failed: {update_e}"
                )
        return False


def rerun_ocr_on_page(page_id: int, rotation_angle: int) -> bool:
    """
    Re-runs the OCR process on a single page, applying a specified rotation.
    This is used when the user manually corrects the orientation of a page.
    """
    logging.info(
        f"--- Re-running OCR for Page ID: {page_id} with rotation {rotation_angle} ---"
    )
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            page = cursor.execute(
                "SELECT processed_image_path FROM pages WHERE id = ?", (page_id,)
            ).fetchone()

            if not page:
                logging.error(f"  - No page found with ID {page_id}")
                return False

            image_path = page["processed_image_path"]
            if not os.path.exists(image_path):
                logging.error(f"  - Image file not found at {image_path}")
                return False

            new_ocr_text = ""
            try:
                with Image.open(image_path) as img:
                    # PIL rotates counter-clockwise. A negative angle is used to match
                    # typical UI expectations of clockwise rotation.
                    rotated_image = img.rotate(-rotation_angle, expand=True)
                    rotated_image.save(image_path, "PNG")
                    logging.info(f"  - Physically rotated and saved image at {image_path}")

                    reader = EasyOCRSingleton.get_reader()
                    ocr_results = reader.readtext(np.array(rotated_image))
                    new_ocr_text = " ".join([text for _, text, _ in ocr_results])
            except IOError as e:
                logging.error(f"  - Could not open or process image {image_path}: {e}")
                return False

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


def _get_page_number_from_ai(page_text: str) -> Optional[int]:
    """
    Asks the AI to find the printed page number from the page's text.
    """
    prompt = f"""
Analyze the following text from a single page.
What is the printed page number?
Your response MUST be an integer (e.g., \"1\", \"2\", \"3\") or the word \"none\" if no page number is found.
Do not provide any other text or explanation.

---
PAGE TEXT:
{page_text[:3000]}
---
END PAGE TEXT:
"""
    result = _query_ollama(prompt, timeout=30)
    if result is None:
        return None  # AI connection error

    # Search for the first sequence of digits in the AI's response
    match = re.search(r"\d+", result)
    if match:
        try:
            return int(match.group(0))
        except ValueError:
            return None
    return None


def get_ai_suggested_order(pages: List[Dict]) -> List[int]:
    """Determines a suggested page order for a document by asking the AI to find
    the printed page number on each page."""
    logging.info(f"--- Starting 'Extract, then Sort' for {len(pages)} pages ---")
    numbered_pages = []
    unnumbered_pages = []

    for page in pages:
        page_id = page["id"]
        logging.info(f"  - Extracting page number from Page ID: {page_id}...")
        extracted_num = _get_page_number_from_ai(page["ocr_text"])
        if extracted_num is not None:
            logging.info(f"    - AI found page number: {extracted_num}")
            numbered_pages.append({"id": page_id, "num": extracted_num})
        else:
            logging.info("    - AI found no page number.")
            unnumbered_pages.append({"id": page_id})

    # Sort pages with an extracted number by that number
    numbered_pages.sort(key=lambda p: p["num"])
    sorted_numbered_ids = [p["id"] for p in numbered_pages]
    logging.info(f"\n  - Sorted numbered pages: {sorted_numbered_ids}")

    # Append all unnumbered pages at the end
    unnumbered_ids = [p["id"] for p in unnumbered_pages]
    logging.info(f"  - Unnumbered pages (will be appended): {unnumbered_ids}")

    final_order = sorted_numbered_ids + unnumbered_ids
    logging.info(f"--- 'Extract, then Sort' complete. Final order: {final_order} ---")
    return final_order


def get_ai_suggested_filename(document_text: str, category: str) -> str:
    """Asks the AI to generate a descriptive filename for the document."""
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

---
DOCUMENT TEXT (Category: '{category}'):
{document_text[:6000]}
---
END DOCUMENT TEXT:
"""
    ai_title = _query_ollama(prompt, timeout=90)
    current_date = datetime.now().strftime("%Y-%m-%d")

    if ai_title is None:
        return f"{current_date}_AI-Error-Generating-Name"

    # Clean up the AI's response to be a safe filename
    # Remove common conversational prefixes
    ai_title = re.sub(r'^\s*Here.+?:?\s*', '', ai_title, flags=re.IGNORECASE)
    # Remove any characters that are not alphanumeric, hyphen, or underscore
    sanitized_title = re.sub(r'[^\w\-_]', '', ai_title).strip('-')

    if not sanitized_title:
        sanitized_title = "Untitled-Document"

    return f"{current_date}_{sanitized_title}"


def export_document(
    pages: List[Dict], final_name_base: str, category: str
) -> bool:
    """Exports a final document to the filing cabinet in multiple formats:
    1. A standard, multi-page PDF from the images.
    2. A searchable, multi-page PDF with the OCR text embedded.
    3. A Markdown file containing the full OCR text and metadata."""
    logging.info(f"--- EXPORTING Document: {final_name_base} ---")
    if not config.FILING_CABINET_DIR:
        logging.error(
            "FILING_CABINET_DIR is not set in the .env file. Cannot export."
        )
        return False

    category_dir_name = _sanitize_category(category)
    destination_dir = os.path.join(config.FILING_CABINET_DIR, category_dir_name)
    os.makedirs(destination_dir, exist_ok=True)

    image_paths = [p["processed_image_path"] for p in pages]
    full_ocr_text = "\n\n---\n\n".join([p["ocr_text"] for p in pages])

    try:
        # --- 1. Standard PDF from images ---
        standard_pdf_path = os.path.join(destination_dir, f"{final_name_base}.pdf")
        images_to_save = []
        # Use a list to hold open Image objects
        pil_images = []
        for p in image_paths:
            if os.path.exists(p):
                img = Image.open(p)
                # Convert to RGB if necessary, as some modes aren't supported by PDF saving
                if img.mode != "RGB":
                    img = img.convert("RGB")
                pil_images.append(img)
            else:
                logging.warning(f"Image not found for PDF export: {p}")

        if pil_images:
            pil_images[0].save(
                standard_pdf_path, save_all=True, append_images=pil_images[1:]
            )
            logging.info(f"  - Saved Standard PDF: {standard_pdf_path}")
        # Ensure all image files are closed
        for img in pil_images:
            img.close()

        # --- 2. Searchable PDF with OCR layer ---
        searchable_pdf_path = os.path.join(
            destination_dir, f"{final_name_base}_ocr.pdf"
        )
        with fitz.open() as doc:  # Create a new, empty PDF
            for page_data in pages:
                img_path = page_data["processed_image_path"]
                if not os.path.exists(img_path):
                    logging.warning(f"Image not found for OCR PDF export: {img_path}")
                    continue

                with fitz.open(img_path) as img_doc:
                    rect = img_doc[0].rect
                    # Create a new page in the output PDF with the same dimensions as the image
                    pdf_page = doc.new_page(width=rect.width, height=rect.height)
                    # Place the image on the page
                    pdf_page.insert_image(rect, filename=img_path)
                    # Add the OCR text as an invisible text layer (render_mode=3)
                    # This makes the text selectable and searchable.
                    pdf_page.insert_text((0, 0), page_data["ocr_text"], render_mode=3)

            if doc.page_count > 0:
                # Save with garbage collection and compression for smaller file size
                doc.save(searchable_pdf_path, garbage=4, deflate=True)
                logging.info(f"  - Saved Searchable PDF: {searchable_pdf_path}")

        # --- 3. Markdown Log File ---
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
    """
    Deletes the temporary directory containing the processed images for a batch.
    This is called after a batch has been successfully exported and finalized.
    """
    logging.info(f"--- CLEANING UP Batch ID: {batch_id} ---")
    if not config.PROCESSED_DIR:
        logging.error("PROCESSED_DIR environment variable is not set.")
        return False

    batch_image_dir = os.path.join(config.PROCESSED_DIR, str(batch_id))
    if os.path.isdir(batch_image_dir):
        try:
            shutil.rmtree(batch_image_dir)
            logging.info(
                f"  - Successfully deleted temporary directory: {batch_image_dir}"
            )
            return True
        except OSError as e:
            logging.error(f"  - Failed to delete directory {batch_image_dir}: {e}")
            return False
    else:
        logging.info(f"  - Directory not found, skipping cleanup: {batch_image_dir}")
        return True
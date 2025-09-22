"""This module contains the core business logic for the document processing pipeline.
It handles the heavy lifting of the application, including:

- **File Conversion**: Converting source PDFs into processable PNG images.
- **OCR (Optical Character Recognition)**: Extracting text from the images using
  both Tesseract for orientation detection and EasyOCR for the main text extraction.
- **AI Integration**: Communicating with a local LLM (via Ollama) to perform
  tasks like document classification, page number extraction, and filename suggestion.
- **File Export**: Generating the final output files, including a standard PDF,
  a searchable PDF with an invisible text layer, and a detailed Markdown log file.
- **File System Management**: Handling the creation of temporary directories,
  moving processed files to an archive, and cleaning up temporary files after export.

This module is designed to be called by the Flask application (`app.py`) and
interacts with the database via the functions in `database.py`. It is the
engine of the application.
"""
# Standard library imports
import os
import sqlite3
import shutil
import re
import warnings
from datetime import datetime

# Third-party imports
import requests
import numpy as np
from dotenv import load_dotenv
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import easyocr
import fitz  # PyMuPDF, used for creating searchable PDFs

# --- INITIAL SETUP ---

# Load environment variables from a .env file. This is crucial for configuration
# without hardcoding paths or API keys directly in the code.
load_dotenv()

# Suppress a specific, non-critical warning from PyTorch (a dependency of EasyOCR).
# This warning is related to memory pinning and is not relevant to the core
# functionality of this application, so it's hidden to keep the console output clean.
warnings.filterwarnings("ignore", message=".*'pin_memory' argument is set as true.*" )

# Initialize the EasyOCR reader. This can be a time-consuming operation as it
# loads the language model into memory. It's done once when the module is first
# imported to avoid re-loading it for every OCR task.
print("Initializing EasyOCR Reader (this may take a moment)...")
# We specify English ('en') as the language and disable GPU usage for broader
# compatibility, as not all systems have a compatible GPU.
reader = easyocr.Reader(["en"], gpu=False)
print("EasyOCR Reader initialized.")

# A predefined list of broad categories for the AI to use for its initial
# classification guess. This provides a controlled vocabulary and ensures
# consistency in the AI's suggestions.
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


# --- CORE PROCESSING FUNCTIONS ---

def _process_single_page_from_file(
    cursor,
    image_path,
    batch_id,
    source_filename,
    page_num
):
    """
    Processes a single page image: performs OCR, detects orientation, and saves
    the results to the database. This is a helper function for `process_batch`.

    Args:
        cursor (sqlite3.Cursor): The database cursor for executing queries.
        image_path (str): The file path to the PNG image of the page.
        batch_id (int): The ID of the batch this page belongs to.
        source_filename (str): The name of the original PDF file.
        page_num (int): The page number within the original PDF.

    Returns:
        bool: True if processing was successful, False otherwise.
    """
    try:
        print(
            f"  - Processing Page {page_num} from file: {os.path.basename(image_path)}"
        )
        # A debug flag to skip the time-consuming OCR step for faster testing.
        skip_ocr = os.getenv("DEBUG_SKIP_OCR", "False").lower() in ("true", "1", "t")
        if skip_ocr:
            print("    - DEBUG_SKIP_OCR is True. Skipping OCR and rotation.")
            ocr_text = f"OCR SKIPPED FOR DEBUG - Page {page_num} of {source_filename}"
            rotation = 0
        else:
            # Use Tesseract's Orientation and Script Detection (OSD) to find the
            # correct orientation of the page.
            try:
                if not os.path.exists(image_path):
                    print(f"    - [ERROR] Image file {os.path.basename(image_path)} is missing before opening.")
                    return False
                file_size = os.path.getsize(image_path)
                if file_size == 0:
                    print(f"    - [ERROR] Image file {os.path.basename(image_path)} is empty before opening.")
                    return False
                print(f"    - DEBUG: Attempting to open {os.path.basename(image_path)} (size: {file_size} bytes).")
                image = Image.open(image_path)
            except Exception as img_e:
                print(f"    - [ERROR] Could not open image {os.path.basename(image_path)}: {img_e}")
                return False
            
            osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
            rotation = osd.get("rotate", 0)
            # If Tesseract suggests a rotation, apply it before performing OCR.
            if rotation > 0:
                print(f"    - Rotating page by {rotation} degrees.")
                image = image.rotate(rotation, expand=True)
                image.save(image_path, "PNG")  # Overwrite the image with the correct orientation.

            # Perform the main OCR task using EasyOCR.
            print("    - Performing OCR...")
            ocr_results = reader.readtext(np.array(image))
            # Join the text fragments from EasyOCR into a single string.
            ocr_text = " ".join([text for _, text, _ in ocr_results])

        # Insert the extracted data into the 'pages' table in the database.
        cursor.execute(
            "INSERT INTO pages (batch_id, source_filename, page_number, processed_image_path, ocr_text, status, rotation_angle) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                batch_id,
                source_filename,
                page_num,
                image_path,
                ocr_text,
                "pending_verification",  # The initial status for all new pages.
                rotation,
            ),
        )
        return True
    except Exception as e:
        print(
            f"    - [ERROR] Failed to process Page {page_num} from file {os.path.basename(image_path)}: {e}"
        )
        # If processing fails, delete the temporary image file to avoid orphans.
        if os.path.exists(image_path):
            os.remove(image_path)
        return False


def get_ai_classification(page_text, seen_categories):
    """
    Uses a local LLM (via the Ollama API) to suggest a category for the page's text.

    Args:
        page_text (str): The OCR text extracted from the page.
        seen_categories (list): Not currently used, but could be used to provide
                                context of previous categories in the batch.

    Returns:
        str: The category name suggested by the AI, or a default/error value.
    """
    ollama_host = os.getenv("OLLAMA_HOST")
    ollama_model = os.getenv("OLLAMA_MODEL")
    # This prompt is carefully engineered to constrain the AI's response.
    # It explicitly tells the model to ONLY choose from the provided list and
    # to avoid any conversational filler.
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
            timeout=60,  # A generous timeout for the AI to respond.
        )
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx).
        response_json = response.json()
        # Clean up the AI's response, removing whitespace and common unwanted characters.
        category = response_json.get("response", "Other").strip().strip('"`')
        # Validate that the AI's response is one of the allowed categories.
        # This prevents the model from hallucinating new, invalid categories.
        if category not in BROAD_CATEGORIES:
            print(
                f"  [AI WARNING] Model returned invalid category: '{category}'. Defaulting to 'Other'."
            )
            return "Other"
        return category
    except requests.exceptions.RequestException as e:
        print(f"  [AI ERROR] Could not connect to Ollama: {e}")
        return "AI_Error"  # Return a specific error string for the UI.


def process_batch():
    """
    The main orchestrator function to process a new batch of documents.
    It finds all PDFs in the INTAKE_DIR, converts them to images, processes each
    page, and then runs the initial AI classification.
    """
    print("--- Starting New Batch ---")
    db_path = os.getenv("DATABASE_PATH")
    conn = None
    batch_id = -1  # Initialize batch_id to a known invalid value.
    cursor = None # Initialize cursor to None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Create a new batch record in the database to associate all subsequent pages with.
        cursor.execute("INSERT INTO batches (status) VALUES ('pending_verification')")
        batch_id = cursor.lastrowid
        conn.commit()
        print(f"Created new batch with ID: {batch_id}")

        # Get directory paths from environment variables.
        intake_dir = os.getenv("INTAKE_DIR")
        if intake_dir is None:
            print("[ERROR] INTAKE_DIR environment variable is not set.")
            return False
        processed_dir = os.getenv("PROCESSED_DIR")
        archive_dir = os.getenv("ARCHIVE_DIR")
        if archive_dir is None:
            print("[ERROR] ARCHIVE_DIR environment variable is not set.")
            return False
        os.makedirs(archive_dir, exist_ok=True) # Ensure archive directory exists
        # Create a dedicated subdirectory for this batch's images to keep them organized.
        batch_image_dir = os.path.join(processed_dir, str(batch_id))
        os.makedirs(batch_image_dir, exist_ok=True)

        # Process each PDF file found in the intake directory.
        pdf_files = [f for f in os.listdir(intake_dir) if f.lower().endswith(".pdf")]
        for filename in pdf_files:
            source_pdf_path = os.path.join(intake_dir, filename)
            print(f"\nProcessing file: {filename}")
            # Sanitize the filename to create a safe base for the output image names.
            sanitized_filename = "".join(
                [c for c in os.path.splitext(filename)[0] if c.isalnum() or c in ("-", "_")]
            ).rstrip()

            # Use pdf2image to convert the PDF to a series of PNG images.
            images = convert_from_path(
                source_pdf_path,
                dpi=300,  # Use a high DPI for better OCR quality.
                output_folder=batch_image_dir,
                fmt="png",
                output_file=f"{sanitized_filename}_page",
                thread_count=4,  # Use multiple threads to speed up conversion.
            )
            # Process each generated image file.
            for i, image_path in enumerate(sorted([img.filename for img in images])):
                _process_single_page_from_file(
                    cursor, image_path, batch_id, filename, i + 1
                )
            conn.commit()  # Commit to the database after each PDF is fully processed.
            print(f"  - Successfully processed and saved {len(images)} pages.")
            # Move the original PDF to the archive directory to prevent re-processing.
            shutil.move(source_pdf_path, os.path.join(archive_dir, filename))
            print("  - Archived original file.")

        # After all PDFs are processed, run the AI classification on all new pages.
        print("\n--- Starting AI 'First Guess' Classification ---")
        cursor.execute("SELECT id, ocr_text FROM pages WHERE batch_id = ?", (batch_id,))
        pages_to_classify = cursor.fetchall()
        for page_id, ocr_text in pages_to_classify:
            print(f"  - Classifying Page ID: {page_id}")
            ai_category = get_ai_classification(ocr_text, [])
            cursor.execute(
                "UPDATE pages SET ai_suggested_category = ? WHERE id = ?",
                (ai_category, page_id),
            )
        conn.commit()

        print("\n--- Batch Processing Complete ---")
        return True
    except Exception as e:
        print(f"[CRITICAL ERROR] An error occurred during batch processing: {e}")
        # If a critical error occurs, mark the batch as 'failed' in the database.
        if conn and batch_id != -1:
            cursor.execute(
                "UPDATE batches SET status = 'failed' WHERE id = ?", (batch_id,)
            )
            conn.commit()
        return False
    finally:
        if conn:
            conn.close()


def rerun_ocr_on_page(page_id, rotation_angle):
    """
    Re-runs the OCR process on a single page, applying a user-specified rotation.
    This is useful for correcting pages that were scanned upside down or sideways.

    Args:
        page_id (int): The ID of the page to re-process.
        rotation_angle (int): The angle (0, 90, 180, 270) to rotate the image by.
    """
    print(f"--- Re-running OCR for Page ID: {page_id} with rotation {rotation_angle} ---")
    db_path = os.getenv("DATABASE_PATH")
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # Get the image path from the database.
        result = cursor.execute(
            "SELECT processed_image_path FROM pages WHERE id = ?", (page_id,)
        ).fetchone()
        if not result:
            print(f"  - [ERROR] No page found with ID {page_id}")
            return False
        image_path = result["processed_image_path"]
        if not os.path.exists(image_path):
            print(f"  - [ERROR] Image file not found at {image_path}")
            return False

        # Open the image, rotate it, and save it, overwriting the original.
        image = Image.open(image_path)
        # Note: PIL rotates counter-clockwise, so we use a negative angle if needed,
        # though for 90/180/270 it often doesn't matter.
        rotated_image = image.rotate(-rotation_angle, expand=True)
        rotated_image.save(image_path, "PNG")
        print(f"  - Physically rotated and saved image at {image_path}")

        # Re-run OCR on the newly rotated image.
        # We convert the PIL image to a NumPy array, which is what EasyOCR expects.
        ocr_results = reader.readtext(np.array(rotated_image))
        new_ocr_text = " ".join([text for _, text, _ in ocr_results])

        # Update the database with the new OCR text and the rotation angle that was applied.
        cursor.execute(
            "UPDATE pages SET ocr_text = ?, rotation_angle = ? WHERE id = ?",
            (new_ocr_text, rotation_angle, page_id),
        )
        conn.commit()
        print("--- OCR Re-run Complete ---")
        return True
    except Exception as e:
        print(f"[CRITICAL ERROR] An error occurred during OCR re-run: {e}")
        return False
    finally:
        if conn:
            conn.close()


# --- AI-ASSISTED ORDERING ---

def _get_page_number_from_ai(page_text):
    """
    A specialized AI call to extract a printed page number from the page's text.
    This is a sub-task for the `get_ai_suggested_order` function.

    Args:
        page_text (str): The OCR text of the page.

    Returns:
        int or None: The extracted page number as an integer, or None if not found.
    """
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
        # Use a regular expression to find the first sequence of digits in the response.
        match = re.search(r"\d+", result)
        if match:
            return int(match.group(0))
        return None
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"[AI SUB-TASK ERROR] Could not get page number: {e}")
        return None


def get_ai_suggested_order(pages):
    """
    Sorts a list of pages using an "Extract, then Sort" strategy.
    It asks the AI for the page number on each page individually, then sorts the
    pages based on the numbers it found. Pages without numbers are appended at the end.

    Args:
        pages (list): A list of page objects (dictionaries or Row objects).

    Returns:
        list: A list of page IDs in the suggested order.
    """
    print(f"--- Starting 'Extract, then Sort' for {len(pages)} pages ---")
    numbered_pages = []
    unnumbered_pages = []
    # For each page, call the AI to find a page number.
    for page in pages:
        page_id = page["id"]
        page_text = page["ocr_text"]
        print(f"  - Extracting page number from Page ID: {page_id}...")
        extracted_num = _get_page_number_from_ai(page_text)
        if extracted_num is not None:
            print(f"    - AI found page number: {extracted_num}")
            numbered_pages.append({"id": page_id, "num": extracted_num})
        else:
            print("    - AI found no page number.")
            unnumbered_pages.append({"id": page_id})

    # Sort the pages that had a number based on that number.
    numbered_pages.sort(key=lambda p: p["num"])
    sorted_numbered_ids = [p["id"] for p in numbered_pages]
    print(f"\n  - Sorted numbered pages: {sorted_numbered_ids}")

    # Append the unnumbered pages to the end of the list.
    unnumbered_ids = [p["id"] for p in unnumbered_pages]
    print(f"  - Unnumbered pages (will be appended): {unnumbered_ids}")

    final_order = sorted_numbered_ids + unnumbered_ids
    print(f"--- 'Extract, then Sort' complete. Final order: {final_order} ---")
    return final_order


# --- FINALIZATION AND EXPORT ---

def get_ai_suggested_filename(document_text, category):
    """
    Uses the LLM to generate a descriptive, filename-safe title for a document.

    Args:
        document_text (str): The concatenated OCR text of all pages in the document.
        category (str): The human-verified category of the document.

    Returns:
        str: A formatted, filename-safe string (e.g., "2023-10-27_Some-Document-Title").
    """
    ollama_host = os.getenv("OLLAMA_HOST")
    ollama_model = os.getenv("OLLAMA_MODEL")

    # This prompt is heavily constrained to force the AI to return only the
    # filename and nothing else. This is a common technique in "prompt engineering".
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

        # Even with a good prompt, add a layer of cleanup as a safeguard.
        # Remove potential conversational prefixes like "Here is the title:".
        ai_title = re.sub(r'^\s*Here.+?:?\s*', '', ai_title, flags=re.IGNORECASE)
        # Sanitize for filename safety, removing any characters that are not
        # word characters, hyphens, or underscores.
        sanitized_title = re.sub(r'[^\w\-_]', '', ai_title).strip('-')

        # Prepend the current date for chronological sorting.
        current_date = datetime.now().strftime("%Y-%m-%d")
        return f"{current_date}_{sanitized_title}"

    except requests.exceptions.RequestException as e:
        print(f"[AI FILENAME ERROR] Could not generate filename: {e}")
        current_date = datetime.now().strftime("%Y-%m-%d")
        return f"{current_date}_AI-Error-Generating-Name"


def export_document(pages, final_name_base, category):
    """
    Generates the three final output files for a single document and saves them
    to the 'filing cabinet' directory.

    Args:
        pages (list): The ordered list of page objects for the document.
        final_name_base (str): The user-approved filename, without extension.
        category (str): The document's category, used for the subfolder name.

    Returns:
        bool: True if export was successful, False otherwise.
    """
    print(f"--- EXPORTING Document: {final_name_base} ---")
    filing_cabinet_dir = os.getenv("FILING_CABINET_DIR")
    if not filing_cabinet_dir:
        print("[ERROR] FILING_CABINET_DIR is not set in the .env file. Cannot export.")
        return False

    # Sanitize the category name to create a valid directory name.
    category_dir_name = "".join(c for c in category if c.isalnum() or c in (' ', '-', '_')).rstrip().replace(' ', '_')
    destination_dir = os.path.join(filing_cabinet_dir, category_dir_name)
    os.makedirs(destination_dir, exist_ok=True)

    image_paths = [p["processed_image_path"] for p in pages]
    full_ocr_text = "\n\n---\n\n".join([p["ocr_text"] for p in pages])

    try:
        # 1. Generate Standard PDF from images. This is a simple, image-only PDF.
        standard_pdf_path = os.path.join(destination_dir, f"{final_name_base}.pdf")
        images = [Image.open(p) for p in image_paths]
        if images:
            # Ensure all images are in RGB format for compatibility with PDF saving.
            rgb_images = [img.convert('RGB') if img.mode != 'RGB' else img for img in images]
            if rgb_images:
                rgb_images[0].save(
                    standard_pdf_path, save_all=True, append_images=rgb_images[1:]
                )
                print(f"  - Saved Standard PDF: {standard_pdf_path}")

        # 2. Generate Searchable PDF with an invisible OCR text layer.
        # This allows the user to search for text in the PDF.
        searchable_pdf_path = os.path.join(destination_dir, f"{final_name_base}_ocr.pdf")
        doc = fitz.open()  # Create a new, empty PDF document with PyMuPDF.
        for page_data in pages:
            img_path = page_data["processed_image_path"]
            ocr_text = page_data["ocr_text"]
            img_doc = fitz.open(img_path)
            rect = img_doc[0].rect
            # Create a new page in our PDF with the same dimensions as the image.
            pdf_page = doc.new_page(width=rect.width, height=rect.height)
            # Place the image on the page.
            pdf_page.insert_image(rect, filename=img_path)
            # Add the OCR text as an invisible layer (`render_mode=3`).
            # This is what makes the PDF searchable.
            pdf_page.insert_text((0, 0), ocr_text, render_mode=3)
            img_doc.close()
        doc.save(searchable_pdf_path, garbage=4, deflate=True)
        doc.close()
        print(f"  - Saved Searchable PDF: {searchable_pdf_path}")

        # 3. Generate a verbose Markdown log file containing all metadata.
        # This provides a human-readable record of the processing.
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
            log_content += f"| {p['id']} | {p['source_filename']} | {p['page_number']} | {p['ai_suggested_category']} |\n"

        log_content += "\n## Full Extracted OCR Text\n\n"
        log_content += "```text\n"
        log_content += f"{full_ocr_text}\n"
        log_content += "```\n"

        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(log_content)
        print(f"  - Saved Markdown Log: {markdown_path}")

        return True

    except Exception as e:
        print(f"[ERROR] Failed to export document {final_name_base}: {e}")
        return False


def cleanup_batch_files(batch_id):
    """
    Deletes the temporary directory containing the intermediate image files for a
    given batch after it has been successfully exported.

    Args:
        batch_id (int): The ID of the batch to clean up.
    """
    print(f"--- CLEANING UP Batch ID: {batch_id} ---")
    processed_dir = os.getenv("PROCESSED_DIR")
    batch_image_dir = os.path.join(processed_dir, str(batch_id))
    if processed_dir is None:
        print("[ERROR] PROCESSED_DIR environment variable is not set.")
        return False
    if os.path.isdir(batch_image_dir):
        try:
            # `shutil.rmtree` recursively deletes a directory and all its contents.
            shutil.rmtree(batch_image_dir)
            print(f"  - Successfully deleted temporary directory: {batch_image_dir}")
            return True
        except OSError as e:
            print(f"  - [ERROR] Failed to delete directory {batch_image_dir}: {e}")
            return False
    else:
        print(f"  - Directory not found, skipping cleanup: {batch_image_dir}")
        return True
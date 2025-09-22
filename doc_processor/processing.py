"""
This module, `processing.py`, is the powerhouse of the document processing application.
It encapsulates all the core business logic and heavy-lifting tasks, acting as the "engine" that drives the pipeline.
It is designed to be called by the web-facing `app.py` and is responsible for:

-   **File Ingestion and Conversion**: Taking raw PDF files from an intake directory and converting each page into a high-resolution PNG image, which is the standard format for OCR processing.
-   **Image Pre-processing and OCR**: Automatically detecting the correct orientation of each page image (e.g., fixing upside-down scans) using Tesseract, and then performing deep-learning-based Optical Character Recognition (OCR) with EasyOCR to extract the text content.
-   **AI Integration and Analysis**: Communicating with a local Large Language Model (LLM) via an Ollama API. This is used for several intelligent tasks:
    -   **Initial Classification**: Providing a "best guess" category for each page based on its text.
    -   **Page Number Extraction**: A specialized task to find printed page numbers to assist with automatic document ordering.
    -   **Filename Suggestion**: Generating a clean, descriptive, and filename-safe title for a completed document.
-   **Final Product Generation**: Creating the final, user-facing output files for each document:
    1.  A standard, image-only PDF.
    2.  A searchable PDF, created by layering the invisible OCR text over the page images using PyMuPDF.
    3.  A detailed Markdown log file containing all metadata and the full extracted text for easy reference.
-   **File System Management**: Handling all file operations, including creating temporary directories for processing, moving original PDFs to an archive, and cleaning up all temporary files once a batch is complete.
"""
# Standard library imports
import os
import sqlite3
import shutil
import re
import warnings
from datetime import datetime

# Third-party imports for core functionality
import requests  # For making HTTP requests to the Ollama AI API.
import numpy as np  # Fundamental for numerical operations, used by OCR libraries for image data.
from dotenv import load_dotenv  # To load configuration from a .env file.
from pdf2image import convert_from_path  # To convert PDF files into images.
from PIL import Image  # Pillow library for advanced image manipulation.
import pytesseract  # For Orientation and Script Detection (OSD).
import easyocr  # The primary OCR engine for text extraction.
import fitz  # PyMuPDF, used for creating the final searchable PDFs.

# --- INITIAL SETUP AND CONFIGURATION ---

# Load environment variables from a .env file into the os.environ dictionary.
# This allows for secure and flexible configuration of file paths and API endpoints.
load_dotenv()

# Suppress a specific, non-critical warning from PyTorch (a dependency of EasyOCR).
# This warning about 'pin_memory' is related to GPU performance optimizations and is not relevant
# for our CPU-based execution. Hiding it keeps the application's console output clean and focused on important messages.
warnings.filterwarnings("ignore", message=".*'pin_memory' argument is set as true.*\)

# Initialize the EasyOCR reader. This is a potentially time-consuming operation as it loads the
# language model into memory. By doing it once when the module is first imported, we ensure it's ready
# to be used by any function without the delay of re-initialization.
print("Initializing EasyOCR Reader (this may take a moment)...")
# We specify English ('en') as the target language and explicitly disable GPU usage (`gpu=False`).
# This ensures the application can run on any machine, even those without a dedicated NVIDIA GPU.
reader = easyocr.Reader(["en"], gpu=False)
print("EasyOCR Reader initialized.")

# A predefined list of broad categories. This list serves as a controlled vocabulary for the AI.
# By instructing the AI to choose only from this list, we ensure consistency in its suggestions
# and prevent it from "hallucinating" new, unwanted categories.
BROAD_CATEGORIES = [
    "Financial Document", "Legal Document", "Personal Correspondence",
    "Technical Document", "Medical Record", "Educational Material",
    "Receipt or Invoice", "Form or Application", "News Article or Publication",
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
    Processes a single page image: performs OCR, detects orientation, saves results to the database.
    This is a private helper function called by `process_batch`.

    Args:
        cursor (sqlite3.Cursor): The active database cursor.
        image_path (str): The file path to the temporary PNG image of the page.
        batch_id (int): The ID of the batch this page belongs to.
        source_filename (str): The name of the original PDF file for tracking.
        page_num (int): The page number of this page within the original PDF.

    Returns:
        bool: True if processing was successful, False otherwise.
    """
    try:
        print(f"  - Processing Page {page_num} from file: {os.path.basename(image_path)}")
        # A debug flag read from environment variables to skip the slow OCR process for faster UI/workflow testing.
        skip_ocr = os.getenv("DEBUG_SKIP_OCR", "False").lower() in ("true", "1", "t")
        if skip_ocr:
            print("    - DEBUG_SKIP_OCR is True. Skipping OCR and rotation.")
            ocr_text = f"OCR SKIPPED FOR DEBUG - Page {page_num} of {source_filename}"
            rotation = 0
        else:
            # Step 1: Use Tesseract's Orientation and Script Detection (OSD) to determine the correct orientation.
            image = Image.open(image_path)
            osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
            rotation = osd.get("rotate", 0)
            
            # Step 2: If Tesseract suggests a rotation, apply it before OCR.
            if rotation > 0:
                print(f"    - Auto-rotating page by {rotation} degrees based on OSD.")
                image = image.rotate(rotation, expand=True)
                image.save(image_path, "PNG")  # Overwrite the image with its corrected orientation.

            # Step 3: Perform the main OCR task using EasyOCR on the correctly oriented image.
            print("    - Performing OCR...")
            ocr_results = reader.readtext(np.array(image)) # EasyOCR works well with NumPy arrays.
            ocr_text = " ".join([text for _, text, _ in ocr_results])

        # Step 4: Insert the extracted data into the 'pages' table in the database.
        cursor.execute(
            "INSERT INTO pages (batch_id, source_filename, page_number, processed_image_path, ocr_text, status, rotation_angle) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (batch_id, source_filename, page_num, image_path, ocr_text, "pending_verification", rotation)
        )
        return True
    except Exception as e:
        print(f"    - [ERROR] Failed to process Page {page_num} from file {os.path.basename(image_path)}: {e}")
        # Clean up the failed image file to prevent orphaned files.
        if os.path.exists(image_path):
            os.remove(image_path)
        return False

def get_ai_classification(page_text, seen_categories):
    """
    Queries a local LLM (via the Ollama API) to suggest a category for the page's text.

    Args:
        page_text (str): The OCR text extracted from the page.
        seen_categories (list): A placeholder for potential future context-aware prompting.

    Returns:
        str: The category name suggested by the AI. Returns "AI_Error" on failure.
    """
    ollama_host = os.getenv("OLLAMA_HOST")
    ollama_model = os.getenv("OLLAMA_MODEL")
    # This prompt is carefully engineered to constrain the AI's response. It explicitly tells the model
    # to ONLY choose from the provided list and to avoid any conversational filler.
    prompt = f"""
    Analyze the following text from a scanned document page. Based on the text, which of the following categories best describes it?
    Available Categories: {', '.join(BROAD_CATEGORIES)}
    Respond with ONLY the single best category name from the list.
    DO NOT provide any explanation, preamble, or summary. Your entire response must be only one of the category names listed above.
    ---
    TEXT TO ANALYZE:
    {page_text[:4000]}  # Truncate text to avoid overly long prompts.
    ---
    """
    try:
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=60,  # A generous timeout for the AI to respond.
        )
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx).
        response_json = response.json()
        # Clean up the AI's response: remove whitespace and common unwanted characters like quotes.
        category = response_json.get("response", "Other").strip().strip('"`')
        
        # Post-validation: Ensure the AI's response is one of the allowed categories.
        # This is a crucial safeguard against the model hallucinating invalid categories.
        if category not in BROAD_CATEGORIES:
            print(f"  [AI WARNING] Model returned invalid category: '{category}'. Defaulting to 'Other'.")
            return "Other"
        return category
    except requests.exceptions.RequestException as e:
        print(f"  [AI ERROR] Could not connect to Ollama: {e}")
        return "AI_Error"  # Return a specific error string for the UI to handle.

def process_batch():
    """
    The main orchestrator function for processing a new batch of documents.
    It finds all PDFs in the INTAKE_DIR, converts them, processes each page, and runs AI classification.
    """
    print("--- Starting New Batch ---")
    db_path = os.getenv("DATABASE_PATH")
    conn = None
    batch_id = -1  # Initialize batch_id to a known invalid value for error handling.
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Step 1: Create a new batch record in the database.
        cursor.execute("INSERT INTO batches (status) VALUES ('pending_verification')")
        batch_id = cursor.lastrowid
        conn.commit()
        print(f"Created new batch with ID: {batch_id}")

        # Step 2: Set up directories.
        intake_dir, processed_dir, archive_dir = (os.getenv(k) for k in ["INTAKE_DIR", "PROCESSED_DIR", "ARCHIVE_DIR"])
        batch_image_dir = os.path.join(processed_dir, str(batch_id))
        os.makedirs(batch_image_dir, exist_ok=True)

        # Step 3: Process each PDF file found in the intake directory.
        pdf_files = [f for f in os.listdir(intake_dir) if f.lower().endswith(".pdf")]
        for filename in pdf_files:
            source_pdf_path = os.path.join(intake_dir, filename)
            print(f"\nProcessing file: {filename}")
            sanitized_filename = "".join([c for c in os.path.splitext(filename)[0] if c.isalnum() or c in ("-", "_")]).rstrip()

            # Use pdf2image to convert the PDF to a series of high-DPI PNG images.
            images = convert_from_path(
                source_pdf_path, dpi=300, output_folder=batch_image_dir,
                fmt="png", output_file=f"{sanitized_filename}_page", thread_count=4
            )
            # Process each generated image file.
            for i, image_path in enumerate(sorted([img.filename for img in images])):
                _process_single_page_from_file(cursor, image_path, batch_id, filename, i + 1)
            
            conn.commit()  # Commit to the database after each PDF is fully processed.
            print(f"  - Successfully processed and saved {len(images)} pages.")
            # Move the original PDF to the archive directory to prevent re-processing it in the future.
            shutil.move(source_pdf_path, os.path.join(archive_dir, filename))
            print("  - Archived original file.")

        # Step 4: After all PDFs are processed, run the AI classification on all new pages in the batch.
        print("\n--- Starting AI 'First Guess' Classification ---")
        cursor.execute("SELECT id, ocr_text FROM pages WHERE batch_id = ?", (batch_id,))
        pages_to_classify = cursor.fetchall()
        for page_id, ocr_text in pages_to_classify:
            print(f"  - Classifying Page ID: {page_id}")
            ai_category = get_ai_classification(ocr_text, [])
            cursor.execute("UPDATE pages SET ai_suggested_category = ? WHERE id = ?", (ai_category, page_id))
        conn.commit()

        print("\n--- Batch Processing Complete ---")
        return True
    except Exception as e:
        print(f"[CRITICAL ERROR] An error occurred during batch processing: {e}")
        # If a critical error occurs, mark the batch as 'failed' in the database for visibility in the UI.
        if conn and batch_id != -1:
            cursor.execute("UPDATE batches SET status = 'failed' WHERE id = ?", (batch_id,))
            conn.commit()
        return False
    finally:
        if conn:
            conn.close()

def rerun_ocr_on_page(page_id, rotation_angle):
    """
    Re-runs the OCR process on a single page, applying a user-specified rotation.
    This is called from the "Review" page to fix incorrectly oriented scans.

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
        # Get the page's image path from the database.
        result = cursor.execute("SELECT processed_image_path FROM pages WHERE id = ?", (page_id,)).fetchone()
        if not result or not os.path.exists(result["processed_image_path"]):
            print(f"  - [ERROR] Image file not found for page ID {page_id}")
            return False
        image_path = result["processed_image_path"]

        # Open the image, apply the specified rotation, and save it, overwriting the original.
        image = Image.open(image_path)
        rotated_image = image.rotate(-rotation_angle, expand=True) # PIL rotates counter-clockwise.
        rotated_image.save(image_path, "PNG")
        print(f"  - Physically rotated and saved image at {image_path}")

        # Re-run OCR on the newly rotated image.
        ocr_results = reader.readtext(np.array(rotated_image))
        new_ocr_text = " ".join([text for _, text, _ in ocr_results])

        # Update the database with the new OCR text and the rotation angle that was applied.
        cursor.execute("UPDATE pages SET ocr_text = ?, rotation_angle = ? WHERE id = ?", (new_ocr_text, rotation_angle, page_id))
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
    A specialized, highly-constrained AI call to extract a printed page number from text.

    Args:
        page_text (str): The OCR text of the page.

    Returns:
        int or None: The extracted page number as an integer, or None if not found.
    """
    prompt = f'''
    Analyze the following text from a single page. What is the printed page number?
    Your response MUST be an integer (e.g., "1", "2", "3") or the word "none" if no page number is found.
    Do not provide any other text or explanation.
    --- PAGE TEXT ---
    {page_text[:3000]}
    --- END PAGE TEXT ---
    '''
    ollama_host, ollama_model = os.getenv("OLLAMA_HOST"), os.getenv("OLLAMA_MODEL")
    try:
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False}, timeout=30
        )
        response.raise_for_status()
        result = response.json().get("response", "none").strip().lower()
        # Use a regular expression to robustly find the first sequence of digits in the AI's response.
        match = re.search(r"\d+", result)
        return int(match.group(0)) if match else None
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"[AI SUB-TASK ERROR] Could not get page number: {e}")
        return None

def get_ai_suggested_order(pages):
    """
    Sorts a list of pages using an "Extract, then Sort" strategy.
    It asks the AI for the page number on each page individually, then sorts the pages based on the numbers it found.

    Args:
        pages (list): A list of page objects (dictionaries or Row objects).

    Returns:
        list: A list of page IDs in the suggested order.
    """
    print(f"--- Starting 'Extract, then Sort' for {len(pages)} pages ---")
    numbered_pages, unnumbered_pages = [], []
    for page in pages:
        print(f"  - Extracting page number from Page ID: {page['id']}...")
        extracted_num = _get_page_number_from_ai(page["ocr_text"])
        if extracted_num is not None:
            print(f"    - AI found page number: {extracted_num}")
            numbered_pages.append({"id": page["id"], "num": extracted_num})
        else:
            print("    - AI found no page number.")
            unnumbered_pages.append({"id": page["id"]})

    # Sort the pages that had a number based on that number.
    numbered_pages.sort(key=lambda p: p["num"])
    # Create the final list by taking the sorted numbered pages first, then appending the unnumbered ones.
    final_order = [p["id"] for p in numbered_pages] + [p["id"] for p in unnumbered_pages]
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
    ollama_host, ollama_model = os.getenv("OLLAMA_HOST"), os.getenv("OLLAMA_MODEL")
    prompt = f'''
    You are a file naming expert. Your ONLY task is to create a filename-safe title from the document text provided.
    RULES:
    - The title MUST be 4-6 words long.
    - Use hyphens (-) instead of spaces.
    - DO NOT include file extensions or the date.
    - DO NOT add ANY introductory text or explanation.
    GOOD EXAMPLE: Brian-McCaleb-Tire-Service-Invoice
    BAD EXAMPLE: Based on the text, a good title would be: Brian-McCaleb-Tire-Service-Invoice
    Your ENTIRE response MUST be ONLY the filename title.
    --- DOCUMENT TEXT (Category: '{category}') ---
    {document_text[:6000]}
    --- END DOCUMENT TEXT ---
    '''
    try:
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False}, timeout=90
        )
        response.raise_for_status()
        ai_title = response.json().get("response", "Untitled-Document").strip()
        # Post-processing as a safeguard: remove common conversational prefixes and sanitize for filename safety.
        ai_title = re.sub(r'^.*?:\\s*', '', ai_title) # Remove prefixes like "Title: "
        sanitized_title = re.sub(r'[^\w\-_]', '', ai_title).strip('-')
        # Prepend the current date for chronological sorting in the file system.
        return f"{datetime.now().strftime('%Y-%m-%d')}_{sanitized_title}"
    except requests.exceptions.RequestException as e:
        print(f"[AI FILENAME ERROR] Could not generate filename: {e}")
        return f"{datetime.now().strftime('%Y-%m-%d')}_AI-Error-Generating-Name"

def export_document(pages, final_name_base, category):
    """
    Generates the three final output files for a single document and saves them.

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

    # Sanitize the category name to create a valid directory name (e.g., "Financial Document" -> "Financial_Document").
    category_dir_name = "".join(c for c in category if c.isalnum() or c in (' ', '-', '_')).rstrip().replace(' ', '_')
    destination_dir = os.path.join(filing_cabinet_dir, category_dir_name)
    os.makedirs(destination_dir, exist_ok=True)

    image_paths = [p["processed_image_path"] for p in pages]
    full_ocr_text = "\n\n---\n\n".join([p["ocr_text"] for p in pages])

    try:
        # 1. Generate Standard PDF from images (a simple, non-searchable, image-only PDF).
        standard_pdf_path = os.path.join(destination_dir, f"{final_name_base}.pdf")
        images = [Image.open(p) for p in image_paths]
        if images:
            rgb_images = [img.convert('RGB') for img in images]
            rgb_images[0].save(standard_pdf_path, save_all=True, append_images=rgb_images[1:])
            print(f"  - Saved Standard PDF: {standard_pdf_path}")

        # 2. Generate Searchable PDF with an invisible OCR text layer using PyMuPDF.
        searchable_pdf_path = os.path.join(destination_dir, f"{final_name_base}_ocr.pdf")
        doc = fitz.open()  # Create a new, empty PDF.
        for page_data in pages:
            img_doc = fitz.open(page_data["processed_image_path"]) # Open the image as a PDF page.
            pdf_page = doc.new_page(width=img_doc[0].rect.width, height=img_doc[0].rect.height)
            pdf_page.insert_image(img_doc[0].rect, stream=img_doc.extract_image(img_doc[0].get_images(full=True)[0]["xref"])["image"])
            # Add the OCR text as an invisible layer (`render_mode=3`). This is the key to making the PDF searchable.
            pdf_page.insert_text((0, 0), page_data["ocr_text"], render_mode=3)
            img_doc.close()
        doc.save(searchable_pdf_path, garbage=4, deflate=True)
        doc.close()
        print(f"  - Saved Searchable PDF: {searchable_pdf_path}")

        # 3. Generate a verbose Markdown log file with all metadata.
        markdown_path = os.path.join(destination_dir, f"{final_name_base}_log.md")
        log_content = f"""# Document Export Log

- **Final Filename**: `{final_name_base}`
- **Category**: `{category}`
- **Export Timestamp**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
- **Total Pages**: {len(pages)}

## Processing Metadata

| Page ID | Source File | Original Page # | AI Suggestion |
|---|---|---|---|
"""
        for p in pages:
            log_content += f"| {p['id']} | {p['source_filename']} | {p['page_number']} | {p['ai_suggested_category']} |
"
        log_content += f"\n## Full Extracted OCR Text

```text
{full_ocr_text}
```
"
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(log_content)
        print(f"  - Saved Markdown Log: {markdown_path}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to export document {final_name_base}: {e}")
        return False

def cleanup_batch_files(batch_id):
    """
    Deletes the temporary directory containing the intermediate image files for a batch.

    Args:
        batch_id (int): The ID of the batch to clean up.
    """
    print(f"--- CLEANING UP Batch ID: {batch_id} ---")
    batch_image_dir = os.path.join(os.getenv("PROCESSED_DIR"), str(batch_id))
    if os.path.isdir(batch_image_dir):
        try:
            shutil.rmtree(batch_image_dir) # Recursively delete the directory and all its contents.
            print(f"  - Successfully deleted temporary directory: {batch_image_dir}")
            return True
        except OSError as e:
            print(f"  - [ERROR] Failed to delete directory {batch_image_dir}: {e}")
            return False
    else:
        print(f"  - Directory not found, skipping cleanup: {batch_image_dir}")
        return True
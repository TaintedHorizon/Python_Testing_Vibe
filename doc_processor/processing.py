# Standard library imports
import os
import sqlite3
import shutil
import re
import warnings

# Third-party imports
import requests
import numpy as np
from dotenv import load_dotenv
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import easyocr

# --- INITIAL SETUP ---

# Load environment variables from a .env file for configuration.
load_dotenv()

# Suppress a specific, non-critical warning from the PyTorch library used by EasyOCR.
warnings.filterwarnings("ignore", message=".*'pin_memory' argument is set as true.*")

# Initialize the EasyOCR reader. This can take a moment as it loads the language model into memory.
# We are using the English language model and disabling GPU usage.
print("Initializing EasyOCR Reader (this may take a moment)...")
reader = easyocr.Reader(["en"], gpu=False)
print("EasyOCR Reader initialized.")

# A predefined list of broad categories for the AI to use for classification.
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
    Processes a single image file: performs OCR and saves the results to the database.

    This internal function is called for each page extracted from a PDF.
    It handles automatic rotation detection, OCR, and database insertion.

    Args:
        cursor (sqlite3.Cursor): The database cursor for executing queries.
        image_path (str): The file path to the PNG image of the page.
        batch_id (int): The ID of the current processing batch.
        source_filename (str): The name of the original PDF file.
        page_num (int): The page number of this page within the original PDF.

    Returns:
        bool: True if processing was successful, False otherwise.
    """
    try:
        print(
            f"  - Processing Page {page_num} from file: {os.path.basename(image_path)}"
        )

        # A debug flag to skip the time-consuming OCR process for faster testing.
        skip_ocr = os.getenv("DEBUG_SKIP_OCR", "False").lower() in ("true", "1", "t")
        if skip_ocr:
            print("    - DEBUG_SKIP_OCR is True. Skipping OCR and rotation.")
            ocr_text = f"OCR SKIPPED FOR DEBUG - Page {page_num} of {source_filename}"
        else:
            # Open the image file.
            image = Image.open(image_path)
            # Use Tesseract's Orientation and Script Detection (OSD) to find the correct orientation.
            osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
            rotation = osd.get("rotate", 0)
            # If rotation is needed, rotate the image and save it back to disk.
            if rotation > 0:
                print(f"    - Rotating page by {rotation} degrees.")
                image = image.rotate(rotation, expand=True)
                image.save(image_path, "PNG")

            # Perform the main OCR task using EasyOCR.
            print("    - Performing OCR...")
            ocr_results = reader.readtext(image_path)
            # Join the recognized text blocks into a single string.
            ocr_text = " ".join([text for _, text, _ in ocr_results])

        # Insert the extracted data into the 'pages' table.
        cursor.execute(
            "INSERT INTO pages (batch_id, source_filename, page_number, processed_image_path, ocr_text, status) VALUES (?, ?, ?, ?, ?, ?)",
            (
                batch_id,
                source_filename,
                page_num,
                image_path,
                ocr_text,
                "pending_verification",  # Initial status for all new pages.
            ),
        )
        return True
    except Exception as e:
        # If any error occurs, print it and clean up the failed image file.
        print(
            f"    - [ERROR] Failed to process Page {page_num} from file {os.path.basename(image_path)}: {e}"
        )
        if os.path.exists(image_path):
            os.remove(image_path)
        return False


def get_ai_classification(page_text, seen_categories):
    """
    Uses a local LLM (via Ollama) to suggest a category for the page text.

    Args:
        page_text (str): The OCR text extracted from the page.
        seen_categories (list): A list of categories already seen in this batch, not currently used but available for future prompt engineering.

    Returns:
        str: The category name suggested by the AI, or a default/error value.
    """
    ollama_host = os.getenv("OLLAMA_HOST")
    ollama_model = os.getenv("OLLAMA_MODEL")

    # This prompt is carefully engineered to force the LLM to respond with only a valid category name.
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
        # Send the request to the Ollama API.
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx).
        response_json = response.json()
        # Clean up the AI's response to remove extra quotes or whitespace.
        category = response_json.get("response", "Other").strip().strip('"`')

        # Validate the AI's response against the allowed list.
        if category not in BROAD_CATEGORIES:
            print(
                f"  [AI WARNING] Model returned invalid category: '{category}'. Defaulting to 'Other'."
            )
            return "Other"
        return category
    except requests.exceptions.RequestException as e:
        print(f"  [AI ERROR] Could not connect to Ollama: {e}")
        return "AI_Error"


def process_batch():
    """
    The main function to process a new batch of documents.

    This function orchestrates the entire pipeline:
    1. Creates a new batch record in the database.
    2. Finds all PDF files in the INTAKE_DIR.
    3. For each PDF, converts it into a series of PNG images.
    4. Processes each page image (rotation, OCR).
    5. Moves the processed PDF to the ARCHIVE_DIR.
    6. Runs AI classification on all newly processed pages.
    """
    print("--- Starting New Batch ---")
    db_path = os.getenv("DATABASE_PATH")
    conn = None
    batch_id = -1
    try:
        # Create a new batch record for this processing run.
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO batches (status) VALUES ('pending_verification')")
        batch_id = cursor.lastrowid
        conn.commit()
        print(f"Created new batch with ID: {batch_id}")

        # Get directory paths from environment variables.
        intake_dir = os.getenv("INTAKE_DIR")
        processed_dir = os.getenv("PROCESSED_DIR")
        archive_dir = os.getenv("ARCHIVE_DIR")
        # Create a subdirectory for this specific batch's images.
        batch_image_dir = os.path.join(processed_dir, str(batch_id))
        os.makedirs(batch_image_dir, exist_ok=True)

        # Find all PDF files in the intake directory.
        pdf_files = [f for f in os.listdir(intake_dir) if f.lower().endswith(".pdf")]
        for filename in pdf_files:
            source_pdf_path = os.path.join(intake_dir, filename)
            print(f"\nProcessing file: {filename}")

            # Sanitize the filename to prevent issues with file paths.
            sanitized_filename = "".join(
                [c for c in os.path.splitext(filename)[0] if c.isalnum() or c in ("-", "_")]
            ).rstrip()

            # Convert PDF to a set of PNG images.
            convert_from_path(
                source_pdf_path,
                dpi=300,
                output_folder=batch_image_dir,
                fmt="png",
                output_file=f"{sanitized_filename}_page",
                thread_count=1,  # Use a single thread to ensure predictable filenames.
            )

            # Get the list of newly created image files.
            page_image_paths = sorted(
                [
                    os.path.join(batch_image_dir, f)
                    for f in os.listdir(batch_image_dir)
                    if f.startswith(f"{sanitized_filename}_page")
                ]
            )

            # Process each page.
            for i, image_path in enumerate(page_image_paths):
                _process_single_page_from_file(
                    cursor,
                    image_path,
                    batch_id,
                    filename,
                    i + 1
                )
            conn.commit()  # Commit after each full PDF is processed.
            print(
                f"  - Successfully processed and saved {len(page_image_paths)} pages."
            )

            # Move the original PDF to the archive directory.
            shutil.move(source_pdf_path, os.path.join(archive_dir, filename))
            print("  - Archived original file.")

        # --- AI First Guess Classification ---
        print("\n--- Starting AI 'First Guess' Classification ---")
        cursor.execute("SELECT id, ocr_text FROM pages WHERE batch_id = ?", (batch_id,))
        pages_to_classify = cursor.fetchall()
        seen_categories = set()
        for page_id, ocr_text in pages_to_classify:
            print(f"  - Classifying Page ID: {page_id}")
            ai_category = get_ai_classification(ocr_text, list(seen_categories))
            if ai_category not in ["AI_Error", "Unreadable"]:
                seen_categories.add(ai_category)
            # Update the database with the AI's suggestion.
            cursor.execute(
                "UPDATE pages SET ai_suggested_category = ? WHERE id = ?",
                (ai_category, page_id),
            )
            conn.commit()

        print("\n--- Batch Processing Complete ---")
        return True
    except Exception as e:
        print(f"[CRITICAL ERROR] An error occurred during batch processing: {e}")
        # If a critical error occurs, mark the batch as 'failed'.
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
    Re-runs the OCR process on a single page, applying a specified rotation.

    This is useful for correcting pages that were scanned upside down or sideways.

    Args:
        page_id (int): The ID of the page to re-process.
        rotation_angle (int): The angle (0, 90, 180, 270) to rotate the image.

    Returns:
        bool: True if successful, False otherwise.
    """
    print(
        f"--- Re-running OCR for Page ID: {page_id} with rotation {rotation_angle} ---"
    )
    db_path = os.getenv("DATABASE_PATH")
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT processed_image_path FROM pages WHERE id = ?", (page_id,)
        )
        result = cursor.fetchone()
        if not result:
            return False

        image_path = result[0]
        if not os.path.exists(image_path):
            return False

        # Open the image, rotate it, and perform OCR again.
        image = Image.open(image_path)
        rotated_image = image.rotate(rotation_angle, expand=True)
        rotated_image_np = np.array(rotated_image)
        ocr_results = reader.readtext(rotated_image_np)
        new_ocr_text = " ".join([text for _, text, _ in ocr_results])

        # Update the database with the new OCR text and the rotation angle that was used.
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


# --- AI ORDERING - NEW "EXTRACT, THEN SORT" METHOD ---

def _get_page_number_from_ai(page_text):
    """
    Performs a focused AI call to extract a printed page number from text.

    This is a sub-task for the page ordering process. It is more reliable
    than asking the AI to sort a whole document at once.

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

        # Use regex to find the first sequence of digits in the AI's response.
        match = re.search(r"\d+", result)
        if match:
            return int(match.group(0))
        return None  # Return None if the response was not a number.
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"[AI SUB-TASK ERROR] Could not get page number: {e}")
        return None


def get_ai_suggested_order(pages):
    """
    Sorts a list of pages using the "Extract, then Sort" strategy.

    This method works in three steps:
    1. It asks the LLM to find the page number on each page individually.
    2. It sorts the pages that had a number found by the AI.
    3. It appends the unnumbered pages to the end of the sorted list.

    Args:
        pages (list): A list of page objects (as dictionaries) to be sorted.

    Returns:
        list: A list of page IDs in the suggested order.
    """
    print(f"--- Starting 'Extract, then Sort' for {len(pages)} pages ---")

    numbered_pages = []
    unnumbered_pages = []

    # Step 1: Loop through each page and ask the AI to find its number.
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

    # Step 2: Sort the pages that had numbers based on the number found.
    numbered_pages.sort(key=lambda p: p["num"])
    sorted_numbered_ids = [p["id"] for p in numbered_pages]
    print(f"\n  - Sorted numbered pages: {sorted_numbered_ids}")

    # The unnumbered pages are simply appended at the end in their original order.
    unnumbered_ids = [p["id"] for p in unnumbered_pages]
    print(f"  - Unnumbered pages (will be appended): {unnumbered_ids}")

    # Step 3: Combine the sorted numbered pages with the unnumbered pages.
    final_order = sorted_numbered_ids + unnumbered_ids
    print(f"--- 'Extract, then Sort' complete. Final order: {final_order} ---")

    return final_order
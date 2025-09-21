import os
import sqlite3
import shutil

import requests
import numpy as np
import re
from dotenv import load_dotenv
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import easyocr
import warnings

# --- INITIAL SETUP ---
load_dotenv()
warnings.filterwarnings("ignore", message=".*'pin_memory' argument is set as true.*")
print("Initializing EasyOCR Reader (this may take a moment)...")
reader = easyocr.Reader(["en"], gpu=False)
print("EasyOCR Reader initialized.")

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

# ... The first several functions (_process_single_page_from_file, get_ai_classification, process_batch, rerun_ocr_on_page) remain unchanged ...


def _process_single_page_from_file(
    cursor, image_path, batch_id, source_filename, page_num
):
    try:
        print(
            f"  - Processing Page {page_num} from file: {os.path.basename(image_path)}"
        )
        skip_ocr = os.getenv("DEBUG_SKIP_OCR", "False").lower() in ("true", "1", "t")
        if skip_ocr:
            print("    - DEBUG_SKIP_OCR is True. Skipping OCR and rotation.")
            ocr_text = f"OCR SKIPPED FOR DEBUG - Page {page_num} of {source_filename}"
        else:
            image = Image.open(image_path)
            osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
            rotation = osd.get("rotate", 0)
            if rotation > 0:
                print(f"    - Rotating page by {rotation} degrees.")
                image = image.rotate(rotation, expand=True)
                image.save(image_path, "PNG")
            print("    - Performing OCR...")
            ocr_results = reader.readtext(image_path)
            ocr_text = " ".join([text for _, text, _ in ocr_results])
        cursor.execute(
            "INSERT INTO pages (batch_id, source_filename, page_number, processed_image_path, ocr_text, status) VALUES (?, ?, ?, ?, ?, ?)",
            (
                batch_id,
                source_filename,
                page_num,
                image_path,
                ocr_text,
                "pending_verification",
            ),
        )
        return True
    except Exception as e:
        print(
            f"    - [ERROR] Failed to process Page {page_num} from file {os.path.basename(image_path)}: {e}"
        )
        if os.path.exists(image_path):
            os.remove(image_path)
        return False


def get_ai_classification(page_text, seen_categories):
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
            print(
                f"  [AI WARNING] Model returned invalid category: '{category}'. Defaulting to 'Other'."
            )
            return "Other"
        return category
    except requests.exceptions.RequestException as e:
        print(f"  [AI ERROR] Could not connect to Ollama: {e}")
        return "AI_Error"


def process_batch():
    print("--- Starting New Batch ---")
    db_path = os.getenv("DATABASE_PATH")
    conn = None
    batch_id = -1
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO batches (status) VALUES ('pending_verification')")
        batch_id = cursor.lastrowid
        conn.commit()
        print(f"Created new batch with ID: {batch_id}")
        intake_dir = os.getenv("INTAKE_DIR")
        processed_dir = os.getenv("PROCESSED_DIR")
        archive_dir = os.getenv("ARCHIVE_DIR")
        batch_image_dir = os.path.join(processed_dir, str(batch_id))
        os.makedirs(batch_image_dir, exist_ok=True)
        pdf_files = [f for f in os.listdir(intake_dir) if f.lower().endswith(".pdf")]
        for filename in pdf_files:
            source_pdf_path = os.path.join(intake_dir, filename)
            print(f"\nProcessing file: {filename}")
            sanitized_filename = "".join(
                [
                    c
                    for c in os.path.splitext(filename)[0]
                    if c.isalnum() or c in ("-", "_")
                ]
            ).rstrip()
            convert_from_path(
                source_pdf_path,
                dpi=300,
                output_folder=batch_image_dir,
                fmt="png",
                output_file=f"{sanitized_filename}_page",
                thread_count=1,
            )
            page_image_paths = sorted(
                [
                    os.path.join(batch_image_dir, f)
                    for f in os.listdir(batch_image_dir)
                    if f.startswith(f"{sanitized_filename}_page")
                ]
            )
            for i, image_path in enumerate(page_image_paths):
                _process_single_page_from_file(
                    cursor, image_path, batch_id, filename, i + 1
                )
            conn.commit()
            print(
                f"  - Successfully processed and saved {len(page_image_paths)} pages."
            )
            shutil.move(source_pdf_path, os.path.join(archive_dir, filename))
            print("  - Archived original file.")
        print("\n--- Starting AI 'First Guess' Classification ---")
        cursor.execute("SELECT id, ocr_text FROM pages WHERE batch_id = ?", (batch_id,))
        pages_to_classify = cursor.fetchall()
        seen_categories = set()
        for page_id, ocr_text in pages_to_classify:
            print(f"  - Classifying Page ID: {page_id}")
            ai_category = get_ai_classification(ocr_text, list(seen_categories))
            if ai_category not in ["AI_Error", "Unreadable"]:
                seen_categories.add(ai_category)
            cursor.execute(
                "UPDATE pages SET ai_suggested_category = ? WHERE id = ?",
                (ai_category, page_id),
            )
            conn.commit()
        print("\n--- Batch Processing Complete ---")
        return True
    except Exception as e:
        print(f"[CRITICAL ERROR] An error occurred during batch processing: {e}")
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
        image = Image.open(image_path)
        rotated_image = image.rotate(rotation_angle, expand=True)
        rotated_image_np = np.array(rotated_image)
        ocr_results = reader.readtext(rotated_image_np)
        new_ocr_text = " ".join([text for _, text, _ in ocr_results])
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
    Performs a simple, focused AI call to extract a page number from text.
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

        # Try to convert the response to a number
        match = re.search(r"\d+", result)
        if match:
            return int(match.group(0))
        return None  # Return None if it's not a number or says "none"
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"[AI SUB-TASK ERROR] Could not get page number: {e}")
        return None


def get_ai_suggested_order(pages):
    """
    Sorts a list of pages using the "Extract, then Sort" strategy.
    It asks the LLM to find the page number on each page individually.
    """
    print(f"--- Starting 'Extract, then Sort' for {len(pages)} pages ---")

    numbered_pages = []
    unnumbered_pages = []

    # Step 1: Loop through each page and ask the AI to find its number
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

    # Step 2: Sort the pages that had numbers
    numbered_pages.sort(key=lambda p: p["num"])
    sorted_numbered_ids = [p["id"] for p in numbered_pages]
    print(f"\n  - Sorted numbered pages: {sorted_numbered_ids}")

    # The unnumbered pages just get appended at the end in their original order
    unnumbered_ids = [p["id"] for p in unnumbered_pages]
    print(f"  - Unnumbered pages (will be appended): {unnumbered_ids}")

    # Step 3: Combine the lists
    final_order = sorted_numbered_ids + unnumbered_ids
    print(f"--- 'Extract, then Sort' complete. Final order: {final_order} ---")

    return final_order

import os
import sqlite3
import shutil
import json
import requests
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import easyocr
import warnings

# --- INITIAL SETUP ---

# Suppress the specific UserWarning from PyTorch/EasyOCR
warnings.filterwarnings("ignore", message=".*'pin_memory' argument is set as true.*")

# Load environment variables from the .env file
load_dotenv()

# Initialize the Flask application
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize the EasyOCR reader
print("Initializing EasyOCR Reader (this may take a moment)...")
reader = easyocr.Reader(['en'], gpu=False)
print("EasyOCR Reader initialized.")

# --- AI CLASSIFICATION LOGIC ---

# Define the broad categories for the AI's first pass.
BROAD_CATEGORIES = [
    "Financial Document", "Legal Document", "Personal Correspondence",
    "Technical Document", "Medical Record", "Educational Material",
    "Receipt or Invoice", "Form or Application", "News Article or Publication",
    "Other"
]

def get_ai_classification(page_text, seen_categories):
    """
    Gets a 'first guess' classification from the Ollama LLM.
    Includes a list of already seen categories for context.
    """
    ollama_host = os.getenv('OLLAMA_HOST')
    ollama_model = os.getenv('OLLAMA_MODEL')
    
    prompt = f"""
    Analyze the following text from a scanned document page. Based on the text, which of the following categories best describes it?
    
    Available Categories: {', '.join(BROAD_CATEGORIES)}
    
    Context: So far in this batch, we have already seen documents of the following types: {', '.join(seen_categories)}. Please be consistent.
    
    Respond with ONLY the single best category name from the list. For example: "Financial Document".

    ---
    TEXT TO ANALYZE:
    {page_text[:4000]} 
    ---
    """
    
    try:
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=60
        )
        response.raise_for_status()
        
        response_json = response.json()
        category = response_json.get('response', 'Other').strip()
        
        if category not in BROAD_CATEGORIES:
            print(f"  [AI WARNING] Model returned an invalid category: '{category}'. Defaulting to 'Other'.")
            return "Other"
        
        print(f"    - AI classification successful: {category}")
        return category
        
    except requests.exceptions.RequestException as e:
        print(f"  [AI ERROR] Could not connect to Ollama server: {e}")
        return "AI_Error"

# --- CORE PROCESSING LOGIC ---

def process_batch():
    print("--- Starting New Batch ---")
    db_path = os.getenv('DATABASE_PATH')
    conn = None
    batch_id = -1
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO batches (status) VALUES ('processing')")
        batch_id = cursor.lastrowid
        conn.commit()
        print(f"Created new batch with ID: {batch_id}")

        intake_dir = os.getenv('INTAKE_DIR')
        processed_dir = os.getenv('PROCESSED_DIR')
        archive_dir = os.getenv('ARCHIVE_DIR')
        batch_image_dir = os.path.join(processed_dir, str(batch_id))
        os.makedirs(batch_image_dir, exist_ok=True)

        pdf_files = [f for f in os.listdir(intake_dir) if f.lower().endswith('.pdf')]
        print(f"Found {len(pdf_files)} PDF(s) to process.")

        for filename in pdf_files:
            source_pdf_path = os.path.join(intake_dir, filename)
            print(f"\nProcessing file: {filename}")
            pages = convert_from_path(source_pdf_path, 300)

            for i, page_image in enumerate(pages):
                page_num = i + 1
                print(f"  - Processing Page {page_num}...")
                
                try:
                    osd = pytesseract.image_to_osd(page_image, output_type=pytesseract.Output.DICT)
                    rotation = osd.get('rotate', 0)
                    if rotation > 0:
                        print(f"    - Rotating page by {rotation} degrees.")
                        page_image = page_image.rotate(rotation, expand=True)
                except Exception as e:
                    print(f"    - [WARNING] Could not determine page orientation: {e}")

                image_filename = f"page_{page_num}.png"
                processed_image_path = os.path.join(batch_image_dir, image_filename)
                page_image.save(processed_image_path, 'PNG')
                
                print("    - Performing OCR...")
                ocr_results = reader.readtext(processed_image_path)
                ocr_text = " ".join([text for _, text, _ in ocr_results])
                
                cursor.execute(
                    'INSERT INTO pages (batch_id, source_filename, page_number, processed_image_path, ocr_text) VALUES (?, ?, ?, ?, ?)',
                    (batch_id, filename, page_num, processed_image_path, ocr_text)
                )
            
            conn.commit()
            print(f"  - Successfully processed and saved {len(pages)} pages.")
            archive_pdf_path = os.path.join(archive_dir, filename)
            shutil.move(source_pdf_path, archive_pdf_path)
            print(f"  - Archived original file to: {archive_pdf_path}")

        print("\n--- Starting AI 'First Guess' Classification ---")
        cursor.execute("SELECT id, ocr_text FROM pages WHERE batch_id = ?", (batch_id,))
        pages_to_classify = cursor.fetchall()
        
        seen_categories = set()
        for page_id, ocr_text in pages_to_classify:
            print(f"  - Classifying Page ID: {page_id}")
            if not ocr_text or ocr_text.isspace():
                print("    - Skipping page with no OCR text.")
                ai_category = "Unreadable"
            else:
                ai_category = get_ai_classification(ocr_text, list(seen_categories))
            
            if ai_category not in ["AI_Error", "Unreadable"]:
                seen_categories.add(ai_category)

            cursor.execute("UPDATE pages SET ai_suggested_category = ? WHERE id = ?", (ai_category, page_id))
            conn.commit()

        cursor.execute("UPDATE batches SET status = 'complete' WHERE id = ?", (batch_id,))
        conn.commit()
        print("\n--- Batch Processing Complete ---")
        return True

    except Exception as e:
        print(f"[CRITICAL ERROR] An error occurred during batch processing: {e}")
        if conn and batch_id != -1:
            cursor.execute("UPDATE batches SET status = 'failed' WHERE id = ?", (batch_id,))
            conn.commit()
        return False
    finally:
        if conn:
            conn.close()

# --- FLASK ROUTES ---
@app.route('/')
def index():
    message = request.args.get('message')
    return render_template('index.html', message=message)

@app.route('/process_new_batch', methods=['POST'])
def handle_batch_processing():
    success = process_batch()
    if success:
        return redirect(url_for('index', message="Batch processing and AI classification completed successfully!"))
    else:
        return redirect(url_for('index', message="An error occurred during processing."))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
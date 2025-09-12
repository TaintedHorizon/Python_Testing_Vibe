#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Automated Document Processing and Classification Script.

This script monitors an intake directory for new PDF files, extracts their text,
classifies them using a Large Language Model (LLM), and then moves and renames
the original file and a newly created searchable text-only PDF to a
processed directory based on the classification.

Author: Gemini Expert Python Developer
Date: 2025-09-12
"""

import os
import shutil
import datetime
import json
import requests
import fitz  # PyMuPDF

try:
    from config import API_KEY
except ImportError:
    print("Error: config.py not found or API_KEY not set.")
    print("Please create a config.py file with your GEMINI_API_KEY.")
    exit(1)


# --- CONFIGURATION ---
# API key is now imported from config.py

# Directory paths (for Linux server environment)
INTAKE_DIR = "/mnt/scans_intake"
PROCESSED_DIR = "/mnt/scans_processed"

# LLM API Configuration
LLM_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={API_KEY}"
LLM_HEADERS = {"Content-Type": "application/json"}
CATEGORIES = ['invoices', 'receipts', 'reports', 'letters', 'legal', 'medical', 'recipes', 'pictures', 'instruction_manuals', 'other']

# --- CORE FUNCTIONS ---

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extracts all text content from a given PDF file.

    Note: This function uses PyMuPDF (fitz), which is highly effective for
    extracting text from text-based PDFs. For scanned, image-only PDFs,
    a dedicated OCR engine like Tesseract (with a Python wrapper like
    pytesseract) would be required to convert images to text first.

    Args:
        pdf_path: The absolute path to the PDF file.

    Returns:
        A string containing all extracted text from the PDF.
        Returns an empty string if the file cannot be opened or no text is found.
    """
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        return ""
    return text

def classify_document(text: str) -> str:
    """
    Sends extracted text to an LLM for classification.

    The LLM is instructed to return a single-word category in a JSON format.

    Args:
        text: The text content of the document.

    Returns:
        The category string (e.g., 'invoices') or 'other' if classification fails.
    """
    if not text.strip():
        print("Warning: Document text is empty. Classifying as 'other'.")
        return 'other'

    system_instruction = (
        "You are a document classification expert. Analyze the following text "
        "and classify it into one of these four categories: "
        f"{', '.join(CATEGORIES)}. Your response MUST be a JSON object "
        "with a single key 'category' containing only the chosen category name."
    )

    payload = {
        "contents": [{
            "parts": [
                {"text": system_instruction},
                {"text": "---"},
                {"text": text[:8000]}  # Use a slice of text to avoid exceeding token limits
            ]
        }],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.0,
        }
    }

    try:
        response = requests.post(LLM_API_URL, headers=LLM_HEADERS, data=json.dumps(payload))
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # The response from Gemini API with response_mime_type: "application/json"
        # is a JSON object containing the generated text.
        response_data = response.json()
        
        # The actual content is in a nested structure
        generated_text = response_data['candidates'][0]['content']['parts'][0]['text']
        category_data = json.loads(generated_text)
        
        category = category_data.get("category")

        if category in CATEGORIES:
            return category
        else:
            print(f"Warning: LLM returned an unexpected category '{category}'. Defaulting to 'other'.")
            return 'other'

    except requests.exceptions.RequestException as e:
        print(f"Error calling LLM API: {e}")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"Error parsing LLM response: {e}. Response: {response.text}")

    return 'other' # Default category on any failure

def process_document(file_path: str):
    """
    Orchestrates the full processing workflow for a single PDF file.

    Args:
        file_path: The absolute path to the source PDF file.
    """
    print(f"--- Processing file: {os.path.basename(file_path)} ---")

    # 1. Extract text
    extracted_text = extract_text_from_pdf(file_path)
    if not extracted_text:
        print("Processing failed: Could not extract text.")
        # Optionally move to a 'failed' directory
        return

    # 2. Classify document
    category = classify_document(extracted_text)
    print(f"Document classified as: {category}")

    # 3. Prepare new filenames and paths
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    original_filename = os.path.basename(file_path)
    base_filename, _ = os.path.splitext(original_filename)
    
    new_filename = f"{category}_{base_filename}_{timestamp}.pdf"
    new_ocr_filename = f"{category}_{base_filename}_{timestamp}_ocr.pdf"
    
    target_dir = os.path.join(PROCESSED_DIR, category)
    destination_path = os.path.join(target_dir, new_filename)
    ocr_destination_path = os.path.join(target_dir, new_ocr_filename)

    # Ensure the target category directory exists
    if not os.path.exists(target_dir):
        print(f"Error: Target directory does not exist: {target_dir}")
        # As per requirements, we assume folders exist. This is a safeguard.
        return

    try:
        # 4. Move and rename the original file
        shutil.move(file_path, destination_path)
        print(f"Moved original file to: {destination_path}")

        # 5. Generate and save the searchable OCR copy
        with fitz.open() as ocr_pdf:
            # Create a new blank page and insert the text
            page = ocr_pdf.new_page(width=595, height=842) # A4 size
            # Insert text into a rectangle; fitz handles text flow
            page.insert_textbox(page.rect, extracted_text, fontsize=11, fontname="helv")
            ocr_pdf.save(ocr_destination_path)
        print(f"Generated searchable PDF at: {ocr_destination_path}")

    except (IOError, shutil.Error) as e:
        print(f"Error during file operations: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during file processing: {e}")

def main():
    """
    Main function to scan the intake directory and process PDF files.
    """
    print("Starting document processing workflow...")
    if not os.path.exists(INTAKE_DIR):
        print(f"Error: Intake directory not found at '{INTAKE_DIR}'. Exiting.")
        return

    processed_files = 0
    for filename in os.listdir(INTAKE_DIR):
        if filename.lower().endswith(".pdf"):
            file_path = os.path.join(INTAKE_DIR, filename)
            process_document(file_path)
            processed_files += 1
    
    if processed_files == 0:
        print("No new PDF files found in the intake directory.")
    else:
        print(f"Workflow finished. Processed {processed_files} file(s).")

if __name__ == "__main__":
    # Note: For a real-world daemon, this main function would be wrapped
    # in a loop with a sleep interval (e.g., time.sleep(60)) to periodically
    # check the directory.
    main()

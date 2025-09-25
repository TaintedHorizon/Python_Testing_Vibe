"""
This module handles the core backend logic for the document processing pipeline.
It includes functions for:
- Converting PDF files into images.
- Running OCR (Optical Character Recognition) on images to extract text.
- Interacting with an AI model (via Ollama) for tasks like document
  classification, page number extraction, and filename suggestion.
- Managing the p                cursor.execute(
                "INSERT INTO batches (status) VALUES (?)",
                (app_config.STATUS_PENDING_VERIFICATION,)
            )
            batch_id = cursor.lastrowid
            conn.commit()
            logging.info(f"Created new batch with ID: {batch_id}")
            os.makedirs(app_config.ARCHIVE_DIR, exist_ok=True)
            batch_image_dir = os.path.join(app_config.PROCESSED_DIR, str(batch_id)) workflow via a SQLite database.
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
from .config_manager import app_config
from .exceptions import FileProcessingError, OCRError, AIServiceError
from .security import validate_path, sanitize_filename
from .database import get_all_categories, log_interaction
from .document_detector import get_detector, DocumentAnalysis

# --- INTERNAL HELPERS (typing / compatibility) ---
def _doc_new_page(doc: Any, *, width: float, height: float):
    """Create a new page on a PyMuPDF Document with backwards compatibility.

    Newer versions expose `Document.new_page`, older ones used `Document.newPage`.
    Some type stubs shipped with PyMuPDF used historically by Pylance may
    not declare one or the other, triggering a false-positive
    reportAttributeAccessIssue. Centralizing the access here avoids scattering
    per-line `# type: ignore` comments and keeps runtime compatibility.

    Args:
        doc: A PyMuPDF Document instance (dynamic C-extension object).
        width: Page width.
        height: Page height.

    Returns:
        The created page object.
    """
    if hasattr(doc, "new_page"):
        return getattr(doc, "new_page")(width=width, height=height)  # type: ignore[attr-defined]
    if hasattr(doc, "newPage"):
        return getattr(doc, "newPage")(width=width, height=height)  # type: ignore[attr-defined]
    raise AttributeError("Document object lacks new_page/newPage methods (PyMuPDF API change?)")

# --- USER CONTEXT HELPER (stub) ---
def get_current_user_id():
    """
    Returns the current user ID for logging. Replace with real user context if/when available.
    """
    return None  # Replace with actual user ID logic if multi-user

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
        conn = sqlite3.connect(app_config.DATABASE_PATH)
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
    if not app_config.OLLAMA_HOST or not app_config.OLLAMA_MODEL:
        logging.error("[AI ERROR] OLLAMA_HOST or OLLAMA_MODEL is not set.")
        return None
    # Log the AI prompt
    log_interaction(
        batch_id=None,  # Fill in batch_id if available in calling context
        document_id=None,  # Fill in document_id if available in calling context
        user_id=get_current_user_id(),
        event_type="ai_prompt",
        step=None,
        content=prompt,
        notes="Ollama prompt sent"
    )
    try:
        response = requests.post(
            f"{app_config.OLLAMA_HOST}/api/generate",
            json={"model": app_config.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        ai_response = response.json().get("response", "").strip()
        # Log the AI response
        log_interaction(
            batch_id=None,  # Fill in batch_id if available in calling context
            document_id=None,  # Fill in document_id if available in calling context
            user_id=get_current_user_id(),
            event_type="ai_response",
            step=None,
            content=ai_response,
            notes="Ollama response received"
        )
        return ai_response
    except requests.exceptions.RequestException as e:
        logging.error(f"[AI ERROR] Could not connect to Ollama: {e}")
        return None


# --- FILENAME SANITIZATION ---
def _validate_file_type(file_path: str) -> bool:
    """
    Validates that a file is a legitimate PDF by checking its magic numbers and structure.
    
    Args:
        file_path (str): Path to the file to validate
        
    Returns:
        bool: True if file is a valid PDF, False otherwise
    """
    try:
        with open(file_path, 'rb') as f:
            # Check PDF magic number
            header = f.read(4)
            if header != b'%PDF':
                logging.error(f"Invalid PDF header in file: {file_path}")
                return False
            
            # Basic structure validation
            f.seek(0, 2)  # Seek to end
            file_size = f.tell()
            if file_size < 32:  # Minimum size for a valid PDF
                logging.error(f"File too small to be valid PDF: {file_path}")
                return False
            
        return True
    except Exception as e:
        logging.error(f"Error validating file {file_path}: {e}")
        return False

def _sanitize_filename(filename: str) -> str:
    """
    Sanitizes a string to be safe for use as a filename base.
    
    Args:
        filename (str): Original filename to sanitize
        
    Returns:
        str: Sanitized filename
    """
    # Remove any directory components
    filename = os.path.basename(filename)
    
    # Keep only alphanumeric characters, hyphens, and underscores
    sanitized = "".join(
        [c for c in os.path.splitext(filename)[0] if c.isalnum() or c in ("-", "_")]
    ).rstrip()
    
    # If the sanitization results in an empty string, default to "document"
    # Add timestamp for uniqueness
    if not sanitized:
        sanitized = f"document_{int(datetime.now().timestamp())}"
        
    # Enforce maximum length
    MAX_FILENAME_LENGTH = 255
    if len(sanitized) > MAX_FILENAME_LENGTH:
        sanitized = sanitized[:MAX_FILENAME_LENGTH]
        
    return sanitized


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

        if not app_config.DEBUG_SKIP_OCR:
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
                app_config.STATUS_PENDING_VERIFICATION,
                rotation,
            ),
        )
        # Log human review/group action (page added to batch)
        log_interaction(
            batch_id=batch_id,
            document_id=None,
            user_id=get_current_user_id(),
            event_type="human_correction",
            step="review_group",
            content=f"Added page {page_num} from {source_filename} to batch {batch_id}.",
            notes=f"Image path: {image_path}"
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


def process_single_document(file_path: str, suggested_strategy: str = "single_document") -> Optional[int]:
    """
    Process a single PDF document without page decomposition.
    
    This bypasses the traditional batch workflow for documents identified
    as single units. The document is processed as one entity with OCR
    and AI classification applied to the full content.
    
    Args:
        file_path: Path to the PDF file
        suggested_strategy: Processing strategy hint from detection
    
    Returns:
        Document ID if successful, None if failed
    """
    logging.info(f"--- PROCESSING SINGLE DOCUMENT: {file_path} ---")
    
    try:
        filename = os.path.basename(file_path)
        sanitized_name = _sanitize_filename(filename)
        
        with database_connection() as conn:
            cursor = conn.cursor()
            
            # Create a single-document batch
            cursor.execute(
                "INSERT INTO batches (status) VALUES (?)",
                ("complete",)  # Single docs go straight to complete
            )
            batch_id = cursor.lastrowid
            conn.commit()
            
            logging.info(f"Created single-document batch: {batch_id}")
            
            # Extract full text content from PDF for AI classification
            full_text = ""
            page_count = 0
            
            with fitz.open(file_path) as doc:
                page_count = len(doc)
                
                # Extract text from all pages
                for page_num in range(page_count):
                    page = doc[page_num]
                    page_text = page.get_text()
                    full_text += f"\n--- Page {page_num + 1} ---\n{page_text}"
            
            logging.info(f"Extracted text from {page_count} pages")
            
            # Get AI classification for the full document
            ai_category = get_ai_classification_single_document(full_text, filename)
            
            # Create document record with single-document strategy
            cursor.execute(
                """INSERT INTO documents 
                   (batch_id, document_name, status, file_type, processing_strategy, original_file_path)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (batch_id, sanitized_name, "pending_finalization", "pdf", suggested_strategy, file_path)
            )
            document_id = cursor.lastrowid
            conn.commit()
            
            logging.info(f"Created document record: {document_id}")
            
            # Store the document content and classification without pages table
            # This is a simplified storage approach for single documents
            
            # Move original to archive
            archive_path = os.path.join(app_config.ARCHIVE_DIR, filename)
            os.makedirs(app_config.ARCHIVE_DIR, exist_ok=True)
            shutil.move(file_path, archive_path)
            logging.info(f"Archived original to: {archive_path}")
            
            # Log the processing action
            log_interaction(
                batch_id=batch_id,
                document_id=document_id,
                user_id=get_current_user_id(),
                event_type="single_document_processed",
                step="intake",
                content={"strategy": suggested_strategy, "pages": page_count, "ai_category": ai_category},
                notes=f"Single document processed: {filename}"
            )
            
            return document_id
            
    except Exception as e:
        logging.error(f"Error processing single document {file_path}: {e}")
        return None


def get_ai_classification_single_document(content: str, filename: str) -> Optional[str]:
    """
    Get AI classification for a complete single document.
    Uses enhanced prompt designed for full document analysis.
    """
    if not content.strip():
        return None
    
    # Truncate content if too long to fit in context window
    max_chars = 4000  # Leave room for prompt text
    if len(content) > max_chars:
        content = content[:max_chars] + "\n[... content truncated ...]"
    
    prompt = f"""You are analyzing a complete PDF document for categorization.

FILENAME: {filename}

FULL DOCUMENT CONTENT:
{content}

Based on the complete document content and filename, suggest the most appropriate category from this list:
{', '.join(get_all_categories())}

Consider:
1. The document type (invoice, contract, report, letter, etc.)
2. The subject matter and industry
3. The document's primary purpose
4. Any dates or organizational context

Respond with ONLY the category name that best fits this document."""

    try:
        response = _query_ollama(prompt, timeout=30)
        if response:
            # Extract category from response
            response_clean = response.strip().lower()
            available_categories = [cat.lower() for cat in get_all_categories()]
            
            # Find matching category
            for category in available_categories:
                if category in response_clean:
                    return category.title()
            
            # If no exact match, return the response for manual review
            return response.strip()
            
    except Exception as e:
        logging.error(f"Error getting AI classification: {e}")
    
    return None


def get_ai_document_type_analysis(file_path: str, content_sample: str, filename: str, 
                                 page_count: int, file_size_mb: float) -> Optional[Dict]:
    """
    Use LLM to analyze document type (single document vs batch scan).
    
    This function asks the LLM to examine document structure, layout patterns,
    and content to determine if it's a single cohesive document or a batch scan
    of multiple documents.
    
    Args:
        file_path: Path to the PDF file
        content_sample: First ~500-1000 characters of document text
        filename: Name of the file (without path)
        page_count: Number of pages in the document
        file_size_mb: File size in megabytes
    
    Returns:
        Dict with keys: 'classification' ('single_document'|'batch_scan'), 
                       'confidence' (0-100), 'reasoning' (str explanation)
        Or None if LLM is unavailable or analysis fails
    """
    if not content_sample.strip():
        return None
    
    # Truncate content if too long for LLM context
    max_chars = 2000  # Conservative limit to leave room for prompt
    if len(content_sample) > max_chars:
        content_sample = content_sample[:max_chars] + "\n[... content truncated ...]"
    
    prompt = f"""You are analyzing a PDF file to determine if it contains a single document or multiple documents scanned together.

FILE DETAILS:
- Filename: {filename}
- Page Count: {page_count}
- File Size: {file_size_mb:.1f} MB

DOCUMENT CONTENT SAMPLE (first portion):
{content_sample}

ANALYSIS TASK:
Examine the content structure, layout patterns, and text to classify this PDF as either:
1. SINGLE_DOCUMENT: One cohesive document (invoice, contract, report, letter, etc.)
2. BATCH_SCAN: Multiple separate documents scanned together into one PDF

CLASSIFICATION CRITERIA:
- Single documents have consistent formatting, continuous content flow, unified purpose
- Batch scans often show format changes, topic shifts, multiple document headers/footers, scan artifacts
- Consider if the content reads as one document vs. multiple unrelated documents

Your response must be in this EXACT format:
CLASSIFICATION: [SINGLE_DOCUMENT or BATCH_SCAN]
CONFIDENCE: [number from 0-100]
REASONING: [detailed explanation of your analysis]

Be specific about what patterns you observe that led to your conclusion."""

    try:
        response = _query_ollama(prompt, timeout=45)  # Longer timeout for analysis
        
        if not response:
            return None
        
        # Parse LLM response
        lines = response.strip().split('\n')
        classification = None
        confidence = 0
        reasoning = ""
        
        for line in lines:
            line = line.strip()
            if line.startswith('CLASSIFICATION:'):
                classification_text = line.split(':', 1)[1].strip().upper()
                if 'SINGLE_DOCUMENT' in classification_text or 'SINGLE' in classification_text:
                    classification = 'single_document'
                elif 'BATCH_SCAN' in classification_text or 'BATCH' in classification_text:
                    classification = 'batch_scan'
            elif line.startswith('CONFIDENCE:'):
                try:
                    confidence = int(''.join(filter(str.isdigit, line.split(':', 1)[1])))
                    confidence = max(0, min(100, confidence))  # Clamp to 0-100
                except (ValueError, IndexError):
                    confidence = 50  # Default moderate confidence
            elif line.startswith('REASONING:'):
                reasoning = line.split(':', 1)[1].strip()
            elif reasoning and line and not line.startswith(('CLASSIFICATION:', 'CONFIDENCE:')):
                # Continue multi-line reasoning
                reasoning += " " + line
        
        if classification:
            result = {
                'classification': classification,
                'confidence': confidence,
                'reasoning': reasoning or "LLM analysis completed",
                'llm_used': True
            }
            
            logging.info(f"LLM classification for {filename}: {classification} "
                        f"(confidence: {confidence}%) - {reasoning[:100]}...")
            
            # Log successful LLM analysis for training data collection
            log_interaction(
                batch_id=None,
                document_id=None, 
                user_id=get_current_user_id(),
                event_type="llm_detection_analysis",
                step="document_classification", 
                content=f"{{\"filename\": \"{filename}\", \"page_count\": {page_count}, \"file_size_mb\": {file_size_mb}, \"prompt\": \"{prompt[:200]}...\", \"response\": \"{response[:200]}...\", \"parsed_result\": {result}}}",
                notes=f"LLM document type analysis - {classification} ({confidence}%)"
            )
            
            return result
        else:
            logging.warning(f"Could not parse LLM response for {filename}: {response[:200]}...")
            
            # Log failed parsing for debugging
            log_interaction(
                batch_id=None,
                document_id=None,
                user_id=get_current_user_id(), 
                event_type="llm_detection_parse_error",
                step="document_classification",
                content=f"{{\"filename\": \"{filename}\", \"prompt\": \"{prompt[:200]}...\", \"response\": \"{response[:200]}...\", \"error\": \"Could not parse classification\"}}",
                notes="LLM response parsing failed"
            )
            
            return None
            
    except Exception as e:
        logging.error(f"Error getting LLM document type analysis for {filename}: {e}")
        
        # Log LLM analysis errors
        log_interaction(
            batch_id=None,
            document_id=None,
            user_id=get_current_user_id(),
            event_type="llm_detection_error", 
            step="document_classification",
            content=f"{{\"filename\": \"{filename}\", \"error\": \"{str(e)}\", \"prompt\": \"{prompt[:200] if 'prompt' in locals() else 'N/A'}...\"}}",
            notes=f"LLM detection analysis failed: {e}"
        )
        
        return None


def process_batch() -> bool:
    """
    Enhanced batch processing with intelligent document type detection.
    
    This function now analyzes intake files first and routes them to appropriate
    processing strategies:
    1. Single documents bypass page decomposition for efficiency
    2. Batch scans use traditional page-by-page workflow
    3. Mixed intakes are handled according to per-file detection
    
    Returns:
        bool: True if batch processing was successful, False otherwise
    """
    logging.info("--- Starting Enhanced Batch Processing ---")
    
    # Step 1: Analyze all PDF files and determine processing strategies
    try:
        detector = get_detector()
        analyses = detector.analyze_intake_directory(app_config.INTAKE_DIR)
        
        if not analyses:
            logging.info("No PDF files found in intake directory.")
            return True
        
        # Log detection results for transparency
        logging.info(f"--- DOCUMENT ANALYSIS RESULTS ---")
        single_docs = [a for a in analyses if a.processing_strategy == "single_document"]
        batch_scans = [a for a in analyses if a.processing_strategy == "batch_scan"]
        
        logging.info(f"Files to process as single documents: {len(single_docs)}")
        logging.info(f"Files to process as batch scans: {len(batch_scans)}")
        
        for analysis in analyses:
            logging.info(f"  {os.path.basename(analysis.file_path)}: {analysis.processing_strategy} "
                        f"({analysis.page_count} pages, confidence: {analysis.confidence:.2f})")
        
        # Step 2: Process single documents individually (bypass traditional workflow)
        single_doc_ids = []
        for analysis in single_docs:
            logging.info(f"Processing as single document: {os.path.basename(analysis.file_path)}")
            doc_id = process_single_document(analysis.file_path, analysis.processing_strategy)
            if doc_id:
                single_doc_ids.append(doc_id)
                logging.info(f"✓ Single document processed: ID {doc_id}")
            else:
                logging.error(f"✗ Failed to process single document: {analysis.file_path}")
        
        # Step 3: If there are batch scans, process them with traditional workflow
        batch_success = True
        if batch_scans:
            logging.info(f"Processing {len(batch_scans)} files as traditional batch scan...")
            batch_success = _process_batch_traditional([a.file_path for a in batch_scans])
        
        # Summary
        total_files = len(analyses)
        processed_single = len(single_doc_ids)
        processed_batch = len(batch_scans) if batch_success else 0
        
        logging.info(f"--- PROCESSING SUMMARY ---")
        logging.info(f"Total files: {total_files}")
        logging.info(f"Single documents processed: {processed_single}")
        logging.info(f"Batch scan files processed: {processed_batch}")
        logging.info(f"Success rate: {(processed_single + processed_batch) / total_files * 100:.1f}%")
        
        return (processed_single + processed_batch) == total_files
        
    except Exception as e:
        logging.error(f"Error in enhanced batch processing: {e}")
        return False


def _process_batch_traditional(pdf_files_paths: List[str]) -> bool:
    """
    Traditional batch processing workflow for files identified as batch scans.
    
    This maintains the original page-by-page processing logic but only processes
    the specified files rather than scanning the entire intake directory.
    
    Args:
        pdf_files_paths: List of absolute paths to PDF files to process as batch scan
    
    Returns:
        bool: True if batch processing was successful, False otherwise
    """
    logging.info("--- Starting Traditional Batch Processing ---")
    batch_id = -1
    
    # Validate configuration
    required_dirs = {
        "INTAKE_DIR": app_config.INTAKE_DIR,
        "ARCHIVE_DIR": app_config.ARCHIVE_DIR,
        "PROCESSED_DIR": app_config.PROCESSED_DIR
    }
    
    # Check all required directories are configured and accessible
    for dir_name, dir_path in required_dirs.items():
        if not dir_path:
            logging.error(f"{dir_name} environment variable is not set.")
            return False
            
        abs_path = os.path.abspath(dir_path)
        try:
            os.makedirs(abs_path, exist_ok=True)
            if not os.access(abs_path, os.R_OK | os.W_OK):
                logging.error(f"Insufficient permissions for directory: {abs_path}")
                return False
        except OSError as e:
            logging.error(f"Failed to create/access directory {abs_path}: {e}")
            return False
    
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            # Create a new batch record for batch scan processing
            cursor.execute(
                "INSERT INTO batches (status) VALUES (?)",
                (app_config.STATUS_PENDING_VERIFICATION,)
            )
            batch_id = cursor.lastrowid
            conn.commit()
            logging.info(f"Created new batch scan batch with ID: {batch_id}")
            
            log_interaction(
                batch_id=batch_id,
                document_id=None,
                user_id=get_current_user_id(),
                event_type="status_change",
                step="pending_verification",
                content=f"Batch scan batch {batch_id} created.",
                notes=None
            )
            
            os.makedirs(app_config.ARCHIVE_DIR, exist_ok=True)
            batch_image_dir = os.path.join(app_config.PROCESSED_DIR, str(batch_id))
            os.makedirs(batch_image_dir, exist_ok=True)

            # Process only the specified PDF files (batch scan strategy)
            for file_path in pdf_files_paths:
                filename = os.path.basename(file_path)
                logging.info(f"Processing batch scan file: {filename}")
                sanitized_filename = _sanitize_filename(filename)

                # Convert PDF to individual page images (traditional workflow)
                images = convert_from_path(
                    file_path,
                    dpi=300,
                    output_folder=batch_image_dir,
                    fmt="png",
                    output_file=f"{sanitized_filename}_page",
                    thread_count=4,
                )
                image_files = sorted([img.filename for img in images])

                # Process each page individually with OCR
                for i, image_path in enumerate(image_files):
                    if batch_id is not None:
                        _process_single_page_from_file(
                            cursor=cursor,
                            image_path=str(image_path),
                            batch_id=batch_id,
                            source_filename=filename,
                            page_num=i + 1
                        )
                
                conn.commit()  # Commit after each PDF is fully processed
                logging.info(f"✓ Processed {len(images)} pages from {filename}")
                
                # Archive the original file
                try:
                    archive_path = os.path.join(app_config.ARCHIVE_DIR, filename)
                    shutil.move(file_path, archive_path)
                    logging.info(f"✓ Archived to {archive_path}")
                except OSError as move_e:
                    logging.error(f"✗ Failed to archive {filename}: {move_e}")

            # AI Classification for all pages in the batch
            logging.info("--- AI Classification for Batch Scan Pages ---")
            cursor.execute(
                "SELECT id, ocr_text FROM pages WHERE batch_id = ?", (batch_id,)
            )
            pages_to_classify = cursor.fetchall()
            
            for page in pages_to_classify:
                ai_category = get_ai_classification(page["ocr_text"])
                cursor.execute(
                    "UPDATE pages SET ai_suggested_category = ? WHERE id = ?",
                    (ai_category, page["id"]),
                )
                log_interaction(
                    batch_id=batch_id,
                    document_id=None,
                    user_id=get_current_user_id(),
                    event_type="ai_response",
                    step="classify",
                    content=f"AI classified page {page['id']} as '{ai_category}'",
                    notes=None
                )
            
            conn.commit()
            logging.info(f"✓ Traditional batch processing complete for batch {batch_id}")
            return True

    except Exception as e:
        logging.critical(f"Error in traditional batch processing: {e}")
        if batch_id != -1:
            try:
                with database_connection() as conn:
                    conn.execute(
                        "UPDATE batches SET status = ? WHERE id = ?",
                        (app_config.STATUS_FAILED, batch_id),
                    )
                    conn.commit()
            except Exception as update_e:
                logging.error(f"Failed to update batch status to failed: {update_e}")
        return False


def rerun_ocr_on_page(page_id: int, rotation_angle: int) -> bool:
    """
    Re-runs the OCR process on a single page, applying a specified rotation.
    This is used when the user manually corrects the orientation of a page.
    
    Args:
        page_id (int): The ID of the page to process
        rotation_angle (int): Rotation angle in degrees (must be 0, 90, 180, or 270)
        
    Returns:
        bool: True if OCR was successful, False otherwise
        
    Raises:
        ValueError: If rotation_angle is not valid
    """
    # Validate rotation angle
    valid_rotations = {0, 90, 180, 270}
    if rotation_angle not in valid_rotations:
        logging.error(f"Invalid rotation angle: {rotation_angle}. Must be one of {valid_rotations}")
        raise ValueError(f"Rotation angle must be one of {valid_rotations}")
    
    logging.info(
        f"--- Re-running OCR for Page ID: {page_id} with rotation {rotation_angle} ---"
    )
    
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            page = cursor.execute(
                "SELECT processed_image_path, batch_id FROM pages WHERE id = ?", (page_id,)
            ).fetchone()
            
            if not page:
                logging.error(f"Page ID {page_id} not found in database")
                return False

            image_path = page["processed_image_path"]
            if not os.path.exists(image_path):
                logging.error(f"  - Image file not found at {image_path}")
                return False

            new_ocr_text = ""
            try:
                with Image.open(image_path) as img:
                    # Rotate only in-memory for OCR extraction; preserve original stored orientation
                    working_image = img.rotate(-rotation_angle, expand=True) if rotation_angle else img
                    logging.info(f"  - Applied in-memory rotation (not saved) for OCR: {rotation_angle} degrees")
                    reader = EasyOCRSingleton.get_reader()
                    ocr_results = reader.readtext(np.array(working_image))
                    new_ocr_text = " ".join([text for _, text, _ in ocr_results])
            except IOError as e:
                logging.error(f"  - Could not open or process image {image_path}: {e}")
                return False

            cursor.execute(
                "UPDATE pages SET ocr_text = ?, rotation_angle = ? WHERE id = ?",
                (new_ocr_text, rotation_angle, page_id),
            )
            conn.commit()
            # Log human correction event
            log_interaction(
                batch_id=page["batch_id"],
                document_id=None,
                user_id=get_current_user_id(),
                event_type="human_correction",
                step="ocr_correction",
                content=f"Re-ran OCR with rotation {rotation_angle} for page {page_id}.",
                notes=f"Image path: {image_path}"
            )
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
        # Log AI ordering suggestion
        # If page is a sqlite3.Row, convert to dict for .get()
        page_dict = dict(page) if not isinstance(page, dict) else page
        log_interaction(
            batch_id=page_dict.get("batch_id"),
            document_id=page_dict.get("document_id"),
            user_id=get_current_user_id(),
            event_type="ai_response",
            step="order",
            content=f"AI suggested page number {extracted_num} for page {page_id}",
            notes=None
        )
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
    # Log AI filename suggestion
    log_interaction(
        batch_id=None,  # Fill in if available
        document_id=None,  # Fill in if available
        user_id=get_current_user_id(),
        event_type="ai_response",
        step="name",
        content=f"AI suggested filename: {ai_title}",
        notes=None
    )
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
    # Log export event (status_change: finalize/export) after destination_dir is defined
    try:
        # Ensure first page is a dict for .get() access
        first_page = pages[0] if pages else None
        if first_page is not None and not isinstance(first_page, dict):
            first_page = dict(first_page)
        batch_id = first_page.get("batch_id") if first_page and "batch_id" in first_page else None
    except Exception:
        batch_id = None
    # destination_dir is defined below, so move log_interaction after that
    if not app_config.FILING_CABINET_DIR:
        logging.error(
            "FILING_CABINET_DIR is not set in the .env file. Cannot export."
        )
        return False

    category_dir_name = _sanitize_category(category)
    destination_dir = os.path.join(app_config.FILING_CABINET_DIR, category_dir_name)
    os.makedirs(destination_dir, exist_ok=True)

    # Ensure all pages are dicts for safe .get() and key access
    pages = [dict(p) if not isinstance(p, dict) else p for p in pages]
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
                    # Use helper for compatibility + to satisfy static analysis (Pylance)
                    pdf_page = _doc_new_page(doc, width=rect.width, height=rect.height)
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
            # If p is a sqlite3.Row, convert to dict for .get()
            p_dict = dict(p) if not isinstance(p, dict) else p
            log_content += f"| {p_dict['id']} | {p_dict['source_filename']} | {p_dict['page_number']} | {p_dict.get('ai_suggested_category', '')} |\n"

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
    if not app_config.PROCESSED_DIR:
        logging.error("PROCESSED_DIR environment variable is not set.")
        return False

    batch_image_dir = os.path.join(app_config.PROCESSED_DIR, str(batch_id))
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
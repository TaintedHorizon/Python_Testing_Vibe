from typing import Optional  # Early import needed for annotations used before bulk imports

# --- SAFE FILE MOVE UTILITY ---
def safe_move(src, dst):
    """
    Safely move a file with proper error handling and backup preservation.
    Only removes source after successful copy verification.
    """
    import shutil, os
    
    try:
        # Ensure destination directory exists
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        
        # Copy the file first
        shutil.copy2(src, dst)
        
        # Verify the copy was successful by checking size and existence
        if not os.path.exists(dst):
            raise OSError(f"Copy failed - destination file does not exist: {dst}")
        
        src_size = os.path.getsize(src)
        dst_size = os.path.getsize(dst)
        if src_size != dst_size:
            raise OSError(f"Copy failed - size mismatch: src={src_size} dst={dst_size}")
        
        # Only remove source after successful verification
        os.remove(src)
        logging.debug(f"✓ Safe move completed: {os.path.basename(src)} -> {dst}")
        
    except Exception as e:
        # If anything fails, ensure destination is cleaned up (partial copy)
        if os.path.exists(dst):
            try:
                os.remove(dst)
                logging.warning(f"Cleaned up failed copy: {dst}")
            except:
                pass
        raise OSError(f"Safe move failed from {src} to {dst}: {e}")

# --- FILE HASH / DEDUP HELPERS ---
def _file_sha256(path: str, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 hash of a file (streamed) and return hex digest.

    Uses a 1MB chunk size (tunable) to balance speed and memory. Caller should
    ensure path exists. Any exception propagates to allow caller to decide on
    fallback behavior.
    """
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            h.update(chunk)
    return h.hexdigest()

def _files_identical(a: str, b: str) -> bool:
    """Return True if two existing files are byte-identical.

    Fast path: compare size; if different -> False.
    Slow path: compare SHA-256 (streamed). Any hashing error returns False (so
    caller will proceed with copy to be safe).
    """
    try:
        if not (os.path.exists(a) and os.path.exists(b)):
            return False
        if os.path.getsize(a) != os.path.getsize(b):
            return False
        return _file_sha256(a) == _file_sha256(b)
    except Exception:
        return False

def _lookup_forced_rotation(filename: str) -> Optional[int]:
    """Return a persisted forced rotation for the given original intake filename, or None.

    Looks up value from intake_rotations table (if present). Filename is expected
    to match what was stored during /save_rotation (original intake basename).
    Any error returns None silently to avoid disrupting processing.
    """
    try:
        from .database import get_db_connection  # local import to avoid cycles
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS intake_rotations (filename TEXT PRIMARY KEY, rotation INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        row = cur.execute("SELECT rotation FROM intake_rotations WHERE filename = ?", (filename,)).fetchone()
        conn.close()
        if row is None:
            return None
        rot = int(row[0])
        if rot % 360 not in (0, 90, 180, 270):
            return (rot % 360)  # normalize unusual values
        return rot % 360
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return None

# --- IMAGE TO PDF CONVERSION ---
def convert_image_to_pdf(image_path: str, output_pdf_path: str) -> str:
    """
    Convert an image file (PNG, JPG, JPEG) to PDF format.
    
    Args:
        image_path: Path to the source image file
        output_pdf_path: Path where the converted PDF will be saved
        
    Returns:
        str: Path to the created PDF file
        
    Raises:
        FileProcessingError: If conversion fails
    """
    try:
        # Validate input file
        if not os.path.exists(image_path):
            raise FileProcessingError(f"Image file does not exist: {image_path}")
        
        # Check if it's a supported image format
        supported_formats = ['.png', '.jpg', '.jpeg']
        file_ext = os.path.splitext(image_path)[1].lower()
        if file_ext not in supported_formats:
            raise FileProcessingError(f"Unsupported image format: {file_ext}")
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)
        
        logging.info(f"Converting image to PDF: {os.path.basename(image_path)} -> {os.path.basename(output_pdf_path)}")
        
        # Open and process the image
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (required for PDF)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save as PDF
            img.save(output_pdf_path, "PDF", resolution=150.0)
        
        # Verify the PDF was created successfully
        if not os.path.exists(output_pdf_path):
            raise FileProcessingError(f"PDF conversion failed - output file not created: {output_pdf_path}")
        
        # Verify it's a valid PDF by trying to open it
        try:
            with fitz.open(output_pdf_path) as doc:
                if len(doc) == 0:
                    raise FileProcessingError("Converted PDF has no pages")
        except Exception as pdf_error:
            raise FileProcessingError(f"Converted PDF is invalid: {pdf_error}")
        
        logging.info(f"✅ Successfully converted image to PDF: {os.path.basename(output_pdf_path)}")
        return output_pdf_path
        
    except Exception as e:
        # Clean up any partial output
        if os.path.exists(output_pdf_path):
            try:
                os.remove(output_pdf_path)
            except:
                pass
        
        error_msg = f"Failed to convert image {image_path} to PDF: {e}"
        logging.error(error_msg)
        raise FileProcessingError(error_msg)

def process_image_file(image_path: str, batch_id: int) -> str:
    """
    Process an image file by converting it to PDF and moving it to the batch directory.
    
    Args:
        image_path: Path to the source image file
        batch_id: ID of the batch to process the image into
        
    Returns:
        str: Path to the processed PDF file in the batch directory
        
    Raises:
        FileProcessingError: If processing fails
    """
    try:
        # Generate output filename (replace image extension with .pdf)
        filename_base = os.path.splitext(os.path.basename(image_path))[0]
        pdf_filename = f"{filename_base}.pdf"
        
        # Create batch directory structure
        batch_dir = os.path.join(app_config.WIP_DIR, str(batch_id))
        original_pdfs_dir = os.path.join(batch_dir, "original_pdfs")
        os.makedirs(original_pdfs_dir, exist_ok=True)
        
        # Convert image to PDF in the batch directory
        output_pdf_path = os.path.join(original_pdfs_dir, pdf_filename)
        convert_image_to_pdf(image_path, output_pdf_path)
        
        # Archive the original image file
        archive_dir = os.path.join(app_config.ARCHIVE_DIR, f"batch_{batch_id}_images")
        os.makedirs(archive_dir, exist_ok=True)
        
        archived_image_path = os.path.join(archive_dir, os.path.basename(image_path))
        safe_move(image_path, archived_image_path)
        
        logging.info(f"✅ Processed image file: {os.path.basename(image_path)} -> {pdf_filename} (archived to {archive_dir})")
        return output_pdf_path
        
    except Exception as e:
        error_msg = f"Failed to process image file {image_path}: {e}"
        logging.error(error_msg)
        raise FileProcessingError(error_msg)

def is_image_file(file_path: str) -> bool:
    """
    Check if a file is a supported image format.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        bool: True if the file is a supported image format
    """
    supported_extensions = ['.png', '.jpg', '.jpeg']
    file_ext = os.path.splitext(file_path)[1].lower()
    return file_ext in supported_extensions
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
import json
import logging
import os
import re
import shutil
import sqlite3
import warnings
from io import BytesIO
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
from .database import get_all_categories, log_interaction, store_document_tags
from .llm_utils import _query_ollama, extract_document_tags
from .batch_guard import get_or_create_processing_batch
from .document_detector import get_detector, DocumentAnalysis

# --- PDF MANIPULATION FUNCTIONS ---
def create_searchable_pdf(original_pdf_path: str, output_path: str, document_id: Optional[int] = None, forced_rotation: Optional[int] = None) -> tuple[str, float, str]:
    """
    Create a searchable PDF by adding OCR text as an invisible overlay.
    Includes automatic rotation detection for optimal text extraction.
    
    Checks cache first to avoid expensive OCR reprocessing.
    
    Args:
        original_pdf_path: Path to the original PDF file
        output_path: Path where the searchable PDF will be saved
        document_id: Optional document ID to check for cached OCR results
        
    Returns:
        tuple: (full_ocr_text, average_confidence, status_message)
    """
    try:
        # Check cache first if document_id provided
        if document_id:
            try:
                with database_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT ocr_text, ocr_confidence_avg, searchable_pdf_path 
                        FROM single_documents 
                        WHERE id = ? AND ocr_text IS NOT NULL AND searchable_pdf_path IS NOT NULL
                    """, (document_id,))
                    cached_result = cursor.fetchone()
                    
                    if cached_result:
                        ocr_text, confidence, cached_searchable_path = cached_result
                        
                        # Check if the cached searchable PDF exists
                        if cached_searchable_path and os.path.exists(cached_searchable_path):
                            # Copy cached file to new location if different
                            if cached_searchable_path != output_path:
                                import shutil
                                shutil.copy2(cached_searchable_path, output_path)
                                logging.info(f"📋 Copied cached searchable PDF for document {document_id}")
                            
                            logging.info(f"✅ Using cached OCR results for document {document_id} (confidence: {confidence:.3f})")
                            return ocr_text, confidence or 0.0, "success (cached)"
                        else:
                            # Cached entry exists but file is missing - will regenerate
                            logging.info(f"🔄 Cached OCR found but file missing for document {document_id}, regenerating...")
            except Exception as cache_error:
                logging.warning(f"Error checking OCR cache: {cache_error}")
        
        # No cache found or cache invalid, proceed with full OCR processing
        logging.info(f"🔍 Processing OCR for {os.path.basename(original_pdf_path)}...")
        
        # Open the original PDF
        doc = fitz.open(original_pdf_path)
        ocr_text_pages = []
        confidence_scores = []
        rotation_info = []
        
        logging.info(f"Creating searchable PDF for {os.path.basename(original_pdf_path)}...")
        
        # Process each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Convert page to image for OCR
            mat = fitz.Matrix(2.0, 2.0)
            get_pix = getattr(page, 'get_pixmap', None) or getattr(page, 'getPixmap', None)
            if not get_pix:
                raise AttributeError('Page object lacks get_pixmap/getPixmap (PyMuPDF API change?)')
            pix = get_pix(matrix=mat)  # type: ignore[call-arg]
            img_data = pix.tobytes("png")
            from PIL import Image
            import io, tempfile
            img = Image.open(io.BytesIO(img_data))

            # Forced rotation path (skip auto-detect entirely)
            if forced_rotation is not None:
                try:
                    if not app_config.DEBUG_SKIP_OCR:
                        if forced_rotation % 360 != 0:
                            img = img.rotate(-forced_rotation, expand=True)
                        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                        page_text = pytesseract.image_to_string(img)
                        confidences: list[int] = []
                        for conf_val in ocr_data['conf']:
                            try:
                                conf_int = int(conf_val)
                                if conf_int > 0:
                                    confidences.append(conf_int)
                            except (ValueError, TypeError):
                                continue
                        page_confidence = (sum(confidences) / len(confidences)) if confidences else 0
                        ocr_text_pages.append(page_text)
                        confidence_scores.append(page_confidence)
                        rotation_info.append({'page': page_num + 1, 'rotation': forced_rotation % 360, 'confidence': 1.0})
                        if page_text.strip():
                            _add_invisible_text_overlay(page, page_text)
                    else:
                        ocr_text_pages.append(f"[DEBUG MODE - OCR SKIPPED FOR PAGE {page_num + 1}]")
                        confidence_scores.append(100.0)
                        rotation_info.append({'page': page_num + 1, 'rotation': forced_rotation % 360, 'confidence': 1.0})
                except Exception as forced_err:
                    logging.warning(f"Forced rotation OCR failed for page {page_num + 1}: {forced_err}")
                    ocr_text_pages.append(f"[OCR FAILED FOR PAGE {page_num + 1}]")
                    confidence_scores.append(0.0)
                    rotation_info.append({'page': page_num + 1, 'rotation': forced_rotation % 360, 'confidence': 0.0})
                continue  # next page

            # Auto-detect path (existing logic)
            try:
                if not app_config.DEBUG_SKIP_OCR:
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                        img.save(temp_file.name)
                        temp_path = temp_file.name
                    try:
                        best_rotation, rotation_confidence, rotated_text = _detect_best_rotation(temp_path)
                        rotation_info.append({'page': page_num + 1, 'rotation': best_rotation, 'confidence': rotation_confidence})
                        if best_rotation != 0:
                            logging.info(f"  Page {page_num + 1}: Auto-detected rotation {best_rotation}° (confidence: {rotation_confidence:.3f})")
                            img = img.rotate(-best_rotation, expand=True)
                        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                        page_text = pytesseract.image_to_string(img)
                        confidences: list[int] = []
                        for conf_val in ocr_data['conf']:
                            try:
                                conf_int = int(conf_val)
                                if conf_int > 0:
                                    confidences.append(conf_int)
                            except (ValueError, TypeError):
                                continue
                        page_confidence = (sum(confidences) / len(confidences)) if confidences else 0
                        ocr_text_pages.append(page_text)
                        confidence_scores.append(page_confidence)
                        if page_text.strip():
                            _add_invisible_text_overlay(page, page_text)
                    finally:
                        try:
                            os.unlink(temp_path)
                        except Exception:
                            pass
                else:
                    ocr_text_pages.append(f"[DEBUG MODE - OCR SKIPPED FOR PAGE {page_num + 1}]")
                    confidence_scores.append(100.0)
                    rotation_info.append({'page': page_num + 1, 'rotation': 0, 'confidence': 1.0})
            except Exception as ocr_error:
                logging.warning(f"OCR failed for page {page_num + 1}: {ocr_error}")
                ocr_text_pages.append(f"[OCR FAILED FOR PAGE {page_num + 1}]")
                confidence_scores.append(0.0)
                rotation_info.append({'page': page_num + 1, 'rotation': 0, 'confidence': 0.0})
        
        # Save the searchable PDF
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        doc.close()
        
        # Log rotation summary (forced vs auto)
        rotated_pages = [info for info in rotation_info if info['rotation'] != 0]
        if forced_rotation is not None:
            logging.info(f"  📐 Forced rotation {forced_rotation % 360}° applied to {len(rotation_info)} pages (user/intake override)")
        elif rotated_pages:
            logging.info(f"  📐 Auto-rotation applied to {len(rotated_pages)} pages:")
            for info in rotated_pages:
                logging.info(f"    Page {info['page']}: {info['rotation']}° (confidence: {info['confidence']:.3f})")
        
        # Combine results
        full_text = "\n\n".join(ocr_text_pages)
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        
        status_msg = "success"
        if forced_rotation is not None:
            status_msg += f" (forced rotation {forced_rotation % 360}°)"
        elif rotated_pages:
            status_msg += f" (auto-rotated {len(rotated_pages)} pages)"
        
        # Save OCR results to cache if document_id provided
        if document_id:
            try:
                with database_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE single_documents SET 
                            ocr_text = ?, ocr_confidence_avg = ?, searchable_pdf_path = ?
                        WHERE id = ?
                    """, (full_text, avg_confidence, output_path, document_id))
                    conn.commit()
                    logging.info(f"💾 Cached OCR results for document {document_id} (confidence: {avg_confidence:.1f}%)")
            except Exception as cache_error:
                logging.warning(f"Failed to cache OCR results: {cache_error}")
        
        logging.info(f"✓ Created searchable PDF: {output_path} (avg confidence: {avg_confidence:.1f}%)")
        return full_text, avg_confidence, status_msg
        
    except Exception as e:
        logging.error(f"Error creating searchable PDF: {e}")
        return "", 0.0, f"Error: {e}"


def _add_invisible_text_overlay(page, text: str):
    """
    Add invisible OCR text overlay to a PDF page for searchability.
    This is a simplified version - adds text invisibly for search purposes.
    """
    try:
        # Add text invisibly at a small font size and white color
        text_rect = fitz.Rect(0, 0, page.rect.width, 10)
        page.insert_text(
            text_rect.tl,
            text[:500],  # Limit text length to avoid issues
            fontsize=1,  # Very small
            color=(1, 1, 1),  # White (invisible on white background)
            overlay=False
        )
    except Exception as e:
        logging.warning(f"Could not add text overlay: {e}")


# --- ROBUST DATABASE LOGGING HELPER ---
def safe_log_interaction(batch_id, document_id=None, user_id=None, event_type=None, step=None, content=None, notes=None, max_retries=3):
    """
    Safely log interactions with retry logic and graceful failure handling.
    
    This wrapper prevents database lock issues from crashing the processing pipeline.
    """
    for attempt in range(max_retries):
        try:
            log_interaction(batch_id, document_id, user_id, event_type, step, content, notes)
            return  # Success - exit early
        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                logging.warning(f"Failed to log interaction after {max_retries} attempts: {e}")
                return  # Don't crash the pipeline
            else:
                logging.debug(f"Database log attempt {attempt + 1} failed, retrying: {e}")
                import time
                time.sleep(0.1 * (attempt + 1))  # Exponential backoff

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
        from .database import get_db_connection
        conn = get_db_connection()
        yield conn
    except sqlite3.Error as e:
        logging.critical(f"[CRITICAL DATABASE ERROR] {e}")
        # Re-raise the exception to be handled by the calling function
        raise
    finally:
        if conn:
            conn.close()


# --- LLM QUERY FUNCTION ---
def _query_ollama(prompt: str, timeout: int = 45, context_window: int = 4096, task_name: str = "general") -> Optional[str]:
    """
    Queries the Ollama LLM with the given prompt.
    
    Args:
        prompt: The prompt to send to the LLM
        timeout: Timeout in seconds for the request
        context_window: Context window size for the model
        task_name: Name of the task for logging purposes
        
    Returns:
        The LLM response as a string, or None if there was an error
    """
    if not app_config.OLLAMA_HOST or not app_config.OLLAMA_MODEL:
        logging.warning("Ollama not configured - OLLAMA_HOST or OLLAMA_MODEL missing")
        return None
        
    try:
        import ollama
        
        # Create Ollama client
        client = ollama.Client(host=app_config.OLLAMA_HOST)
        
        # Prepare the request
        messages = [{'role': 'user', 'content': prompt}]
        options = {'num_ctx': context_window}
        
        # Make the request
        logging.debug(f"Sending {task_name} request to Ollama model {app_config.OLLAMA_MODEL}")
        response = client.chat(
            model=app_config.OLLAMA_MODEL,
            messages=messages,
            options=options
        )
        
        result = response['message']['content'].strip()
        logging.debug(f"Ollama {task_name} response received: {len(result)} characters")
        return result
        
    except ImportError:
        logging.error("ollama package not installed - run: pip install ollama")
        return None
    except Exception as e:
        logging.error(f"Error querying Ollama for {task_name}: {e}")
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
        safe_log_interaction(
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
    category = _query_ollama(prompt, context_window=app_config.OLLAMA_CTX_CLASSIFICATION, task_name="classification")

    if category is None:
        return "AI_Error"  # Indicates a connection or API error

    if category not in broad_categories:
        logging.warning(
            f"  [AI WARNING] Model returned invalid category: '{category}'. Defaulting to 'Other'.")
        return "Other"

    return category


def process_single_document(file_path: str, suggested_strategy: str = "single_document") -> Optional[int]:
    """
    DEPRECATED: Legacy single document processor that moves files to archive.
    
    ⚠️ WARNING: This function incorrectly moves single documents to archive instead
    of going through proper workflow to category folders. All callers should use
    _process_single_documents_as_batch() instead for correct behavior.
    
    Args:
        file_path: Path to the PDF file
        suggested_strategy: Processing strategy hint from detection
    
    Returns:
        Document ID if successful, None if failed
    """
    logging.warning(f"⚠️ DEPRECATED FUNCTION CALLED: process_single_document({file_path}) - This should use _process_single_documents_as_batch() instead!")
    logging.info(f"--- LEGACY PROCESSING SINGLE DOCUMENT: {file_path} ---")
    
    try:
        filename = os.path.basename(file_path)
        sanitized_name = sanitize_filename(filename)
        
        with database_connection() as conn:
            cursor = conn.cursor()
            
            # Create a single-document batch
            cursor.execute(
                "INSERT INTO batches (status) VALUES (?)",
                (app_config.STATUS_EXPORTED,)  # Single docs go straight to exported
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
                    # Use modern PyMuPDF API if available, else fallback
                    page_text = ""
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
            # Log the processing action
            log_interaction(
                batch_id=batch_id,
                document_id=document_id,
                user_id=get_current_user_id(),
                event_type="single_document_processed",
                step="intake",
                content=json.dumps({"strategy": suggested_strategy, "pages": page_count, "ai_category": ai_category}),
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
        response = _query_ollama(prompt, timeout=app_config.OLLAMA_TIMEOUT, context_window=app_config.OLLAMA_CTX_CATEGORY, task_name="category")
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
    Uses LLM to analyze document type based on content and metadata.
    
    Args:
        file_path: Full path to the PDF file
        content_sample: Sample text from the document
        filename: Base filename for analysis
        page_count: Number of pages in document
        file_size_mb: File size in megabytes
        
    Returns:
        Dict with classification, confidence, reasoning, and llm_used flag
    """
    try:
        # Create structured prompt for LLM analysis
        prompt = f"""You are a document analysis expert. Analyze this document and determine if it should be processed as a SINGLE_DOCUMENT or BATCH_SCAN.

FILE DETAILS:
- Filename: {filename}
- Page Count: {page_count}
- File Size: {file_size_mb:.1f} MB

DOCUMENT CONTENT SAMPLE:
{content_sample[:2000]}

ANALYSIS TASK:
Classify as SINGLE_DOCUMENT or BATCH_SCAN based on:
- Content structure and formatting consistency
- Document flow and topic coherence
- Presence of multiple document headers/footers
- Format changes and scan artifacts

RESPONSE FORMAT:
CLASSIFICATION: [SINGLE_DOCUMENT or BATCH_SCAN]
CONFIDENCE: [0-100]
REASONING: [Detailed explanation of your analysis]

Provide your analysis now:"""

        # Query the LLM
        response = _query_ollama(prompt, timeout=app_config.OLLAMA_TIMEOUT, context_window=app_config.OLLAMA_CTX_CATEGORY, task_name="document_type_analysis")
        
        if not response:
            return None
            
        # Parse the LLM response (handle both plain and markdown formats)
        classification = None
        confidence = 0
        reasoning = None
        lines = response.strip().split('\n')
        
        # Log raw response at DEBUG level to keep it in logs but not spam console
        logging.debug(f"Raw LLM response for {filename}: {response}")
        
        for line in lines:
            line = line.strip()
            # Handle both plain format (CLASSIFICATION:) and markdown format (**CLASSIFICATION:**)
            if line.startswith('CLASSIFICATION:') or line.startswith('**CLASSIFICATION:**'):
                classification_text = line.split(':', 1)[1].strip().replace('*', '').upper()
                if 'SINGLE_DOCUMENT' in classification_text or 'SINGLE' in classification_text:
                    classification = 'single_document'
                elif 'BATCH_SCAN' in classification_text or 'BATCH' in classification_text:
                    classification = 'batch_scan'
            elif line.startswith('CONFIDENCE:') or line.startswith('**CONFIDENCE:**'):
                try:
                    conf_text = line.split(':', 1)[1].strip().replace('*', '')
                    confidence = int(''.join(filter(str.isdigit, conf_text)))
                    confidence = max(0, min(100, confidence))  # Clamp to 0-100
                except (ValueError, IndexError):
                    confidence = 50  # Default moderate confidence
            elif line.startswith('REASONING:') or line.startswith('**REASONING:**'):
                reasoning = line.split(':', 1)[1].strip().replace('*', '')
            elif reasoning is not None and line and not line.startswith(('CLASSIFICATION:', 'CONFIDENCE:', '**CLASSIFICATION:**', '**CONFIDENCE:**')):
                # Continue multi-line reasoning
                reasoning += " " + line

        if classification:
            # Improve fallback: if reasoning is empty, show a more helpful message
            if not reasoning:
                reasoning = "No explanation provided by LLM. Please check prompt or model configuration."
            result = {
                'classification': classification,
                'confidence': confidence,
                'reasoning': reasoning,
                'llm_used': True
            }
            logging.info(f"Document analysis for {filename} - Type: {classification}, Confidence: {confidence}%")
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
            content=f"{{\"filename\": \"{filename}\", \"error\": \"{str(e)}\", \"prompt\": \"N/A\"}}",
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
        
        # Step 2: Process single documents as ONE batch (proper workflow)
        single_batch_id = None
        single_doc_ids = []
        if single_docs:
            logging.info(f"Creating ONE batch for {len(single_docs)} single documents...")
            single_batch_id = _process_single_documents_as_batch(single_docs)
            if single_batch_id:
                logging.info(f"✓ Single documents batch created: ID {single_batch_id}")
                single_doc_ids = [single_batch_id]  # Track the batch, not individual docs
            else:
                logging.error("✗ Failed to create single documents batch")
        
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


def _process_single_documents_as_batch(single_docs: List[DocumentAnalysis]) -> Optional[int]:
    """
    Process multiple single documents using the improved workflow.
    
    New workflow: OCR → Create Searchable PDF → AI Suggestions → Ready for Manipulation
    This preserves document structure and creates proper outputs.
    
    Args:
        single_docs: List of DocumentAnalysis objects for files identified as single documents
        
    Returns:
        int: The batch ID if successful, None if failed
    """
    if not single_docs:
        return None
        
    logging.info(f"Processing {len(single_docs)} single documents with improved workflow...")
    
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            
            # Get or create processing batch (prevents duplicates)
            batch_id = get_or_create_processing_batch()
            
            logging.info(f"Using batch {batch_id} for single documents processing")
            
            # Set up directories
            batch_dir = os.path.join(app_config.PROCESSED_DIR, str(batch_id))
            searchable_dir = os.path.join(batch_dir, "searchable_pdfs")
            os.makedirs(searchable_dir, exist_ok=True)
            
            # Process each single document with improved workflow
            total_documents_processed = 0
            for analysis in single_docs:
                try:
                    filename = os.path.basename(analysis.file_path)
                    base_name = os.path.splitext(filename)[0]
                    logging.info(f"Processing {filename} with improved single document workflow...")
                    
                    # Handle image files - prefer early normalized PDF from analysis if available
                    if is_image_file(analysis.file_path):
                        batch_wip_dir = os.path.join(app_config.WIP_DIR, str(batch_id))
                        original_pdfs_dir = os.path.join(batch_wip_dir, "original_pdfs")
                        os.makedirs(original_pdfs_dir, exist_ok=True)
                        normalized_pdf_candidate = getattr(analysis, 'pdf_path', None)
                        target_pdf_path = os.path.join(original_pdfs_dir, f"{base_name}.pdf")
                        if normalized_pdf_candidate and normalized_pdf_candidate.lower().endswith('.pdf') and os.path.exists(normalized_pdf_candidate):
                            try:
                                if normalized_pdf_candidate != target_pdf_path:
                                    # Skip copy if identical already exists
                                    if os.path.exists(target_pdf_path) and _files_identical(normalized_pdf_candidate, target_pdf_path):
                                        logging.info(f"♻ Skipping copy (identical) normalized PDF for image {filename}")
                                    else:
                                        import shutil
                                        shutil.copy2(normalized_pdf_candidate, target_pdf_path)
                                logging.info(f"♻ Reusing normalized PDF for image {filename} -> {target_pdf_path}")
                            except Exception as reuse_e:
                                logging.warning(f"Failed to reuse normalized PDF for {filename}: {reuse_e}; falling back to fresh conversion")
                                convert_image_to_pdf(analysis.file_path, target_pdf_path)
                        else:
                            logging.info(f"Converting image file {filename} to PDF (no reusable normalized version)")
                            convert_image_to_pdf(analysis.file_path, target_pdf_path)
                        # Archive original image (only once, after we have a PDF secured)
                        try:
                            archive_dir = os.path.join(app_config.ARCHIVE_DIR, f"batch_{batch_id}_images")
                            os.makedirs(archive_dir, exist_ok=True)
                            archived_image_path = os.path.join(archive_dir, filename)
                            if os.path.exists(analysis.file_path):  # may have been moved already
                                safe_move(analysis.file_path, archived_image_path)
                        except Exception as arch_e:
                            logging.warning(f"Archiving original image failed for {filename}: {arch_e}")
                        pdf_path_for_processing = target_pdf_path
                        pdf_filename = f"{base_name}.pdf"
                    else:
                        pdf_path_for_processing = analysis.file_path
                        pdf_filename = filename

                    # --- Pre-OCR Rotation Normalization ---
                    try:
                        forced_rotation = _lookup_forced_rotation(os.path.basename(pdf_filename))
                        if forced_rotation and forced_rotation % 360 in (90, 180, 270):
                            import fitz  # PyMuPDF already in requirements
                            doc_pre = fitz.open(pdf_path_for_processing)
                            # Avoid double rotate: if first page already rotated to desired angle, skip
                            already = (doc_pre[0].rotation if doc_pre.page_count else 0)
                            if already != forced_rotation:
                                for pg in doc_pre:
                                    pg.set_rotation((pg.rotation + forced_rotation) % 360)
                                # Overwrite original path (safe because earlier steps archived originals for images)
                                doc_pre.save(pdf_path_for_processing, incremental=False, deflate=True)
                                logging.info(f"Applied pre-OCR rotation {forced_rotation}° to {pdf_filename}")
                            doc_pre.close()
                    except Exception as pre_rot_err:
                        logging.warning(f"Pre-OCR rotation normalization failed for {pdf_filename}: {pre_rot_err}")
                    
                    # Step 1: Insert document first with basic info (no OCR yet)
                    cursor.execute("""
                        INSERT INTO single_documents (
                            batch_id, original_filename, original_pdf_path,
                            page_count, file_size_bytes, status
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        batch_id, pdf_filename, pdf_path_for_processing,
                        analysis.page_count, int(analysis.file_size_mb * 1024 * 1024),
                        "processing"
                    ))
                    doc_id = cursor.lastrowid
                    conn.commit()  # Commit immediately to save progress
                    
                    # Step 2: Create searchable PDF with OCR (with caching)
                    searchable_pdf_path = os.path.join(searchable_dir, f"{base_name}_searchable.pdf")
                    # After normalization, forced_rotation should be 0 for OCR creation to avoid re-rotating
                    ocr_text, ocr_confidence, ocr_status = create_searchable_pdf(
                        pdf_path_for_processing, searchable_pdf_path, doc_id, forced_rotation=0
                    )
                    
                    if ocr_status != "success" and not ocr_status.startswith("success"):
                        logging.error(f"Failed to create searchable PDF for {filename}: {ocr_status}")
                        continue
                    
                    # Step 3: Get AI suggestions (with caching)
                    ai_category, ai_filename, ai_confidence, ai_summary = _get_ai_suggestions_for_document(
                        ocr_text, filename, analysis.page_count, analysis.file_size_mb, doc_id
                    )
                    
                    # Step 4: Update document with AI analysis results
                    cursor.execute("""
                        UPDATE single_documents SET 
                            ai_suggested_category = ?, ai_suggested_filename = ?,
                            ai_confidence = ?, ai_summary = ?, status = ?
                        WHERE id = ?
                    """, (ai_category, ai_filename, ai_confidence, ai_summary, "ready_for_manipulation", doc_id))
                    conn.commit()  # Commit AI results immediately
                    
                    total_documents_processed += 1
                    logging.info(f"✓ Processed {filename} - Category: {ai_category}, Name: {ai_filename}")
                    
                except Exception as e:
                    logging.error(f"Error processing {analysis.file_path}: {e}")
                    continue
            
            conn.commit()
            
            # Log the batch creation
            safe_log_interaction(
                batch_id=batch_id,
                document_id=None,
                user_id=get_current_user_id(),
                event_type="single_documents_batch_created",
                step="smart_processing",
                content=json.dumps({
                    "documents_processed": total_documents_processed,
                    "workflow": "improved_single_document",
                    "status": "ready_for_manipulation"
                }),
                notes=f"Improved single document workflow - {total_documents_processed} documents ready"
            )
            
            # Update batch status to ready_for_manipulation now that processing is complete
            cursor.execute(
                "UPDATE batches SET status = ? WHERE id = ?",
                (app_config.STATUS_READY_FOR_MANIPULATION, batch_id)
            )
            conn.commit()
            
            logging.info(f"✓ Successfully created batch {batch_id} with {total_documents_processed} documents ready for manipulation")
            return batch_id
            
    except Exception as e:
        logging.error(f"Error creating single documents batch: {e}")
        return None


def _process_single_documents_as_batch_with_progress(single_docs: List[DocumentAnalysis]):
    """
    Process multiple single documents using the improved workflow with progress tracking.
    
    This is a generator function that yields progress updates for real-time tracking.
    
    Args:
        single_docs: List of DocumentAnalysis objects for files identified as single documents
        
    Yields:
        dict: Progress updates with keys like 'batch_id', 'document_start', 'document_complete', 'error'
    """
    if not single_docs:
        return
        
    logging.info(f"Processing {len(single_docs)} single documents with progress tracking...")
    
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            
            # Get or create processing batch (prevents duplicates)
            batch_id = get_or_create_processing_batch()
            
            logging.info(f"Using batch {batch_id} for single documents with progress tracking")
            yield {'batch_id': batch_id}
            
            # Set up directories
            batch_dir = os.path.join(app_config.PROCESSED_DIR, str(batch_id))
            searchable_dir = os.path.join(batch_dir, "searchable_pdfs")
            os.makedirs(searchable_dir, exist_ok=True)
            
            # Process each single document with improved workflow
            total_documents_processed = 0
            for i, analysis in enumerate(single_docs, 1):
                filename = os.path.basename(analysis.file_path)
                base_name = os.path.splitext(filename)[0]
                
                try:
                    # Signal document processing start
                    yield {
                        'document_start': True,
                        'filename': filename,
                        'document_number': i,
                        'total_documents': len(single_docs)
                    }
                    
                    logging.info(f"Processing {filename} with improved single document workflow...")
                    
                    # Handle image files - convert to PDF first
                    if is_image_file(analysis.file_path):
                        batch_wip_dir = os.path.join(app_config.WIP_DIR, str(batch_id))
                        original_pdfs_dir = os.path.join(batch_wip_dir, "original_pdfs")
                        os.makedirs(original_pdfs_dir, exist_ok=True)
                        normalized_pdf_candidate = getattr(analysis, 'pdf_path', None)
                        target_pdf_path = os.path.join(original_pdfs_dir, f"{base_name}.pdf")
                        action_msg = 'Reusing normalized' if (normalized_pdf_candidate and os.path.exists(normalized_pdf_candidate)) else 'Converting'
                        yield {'message': f'{action_msg} image {filename} to PDF...', 'document_number': i, 'total_documents': len(single_docs)}
                        if normalized_pdf_candidate and normalized_pdf_candidate.lower().endswith('.pdf') and os.path.exists(normalized_pdf_candidate):
                            try:
                                if normalized_pdf_candidate != target_pdf_path:
                                    if os.path.exists(target_pdf_path) and _files_identical(normalized_pdf_candidate, target_pdf_path):
                                        logging.info(f"♻ Skipping copy (identical) normalized PDF for image {filename}")
                                    else:
                                        import shutil
                                        shutil.copy2(normalized_pdf_candidate, target_pdf_path)
                                logging.info(f"♻ Reusing normalized PDF for image {filename} -> {target_pdf_path}")
                            except Exception as reuse_e:
                                logging.warning(f"Reuse failed for {filename}: {reuse_e}; converting fresh")
                                convert_image_to_pdf(analysis.file_path, target_pdf_path)
                        else:
                            convert_image_to_pdf(analysis.file_path, target_pdf_path)
                        # Archive original image safely
                        try:
                            archive_dir = os.path.join(app_config.ARCHIVE_DIR, f"batch_{batch_id}_images")
                            os.makedirs(archive_dir, exist_ok=True)
                            archived_image_path = os.path.join(archive_dir, filename)
                            if os.path.exists(analysis.file_path):
                                safe_move(analysis.file_path, archived_image_path)
                        except Exception as arch_e:
                            logging.warning(f"Archiving original image failed for {filename}: {arch_e}")
                        pdf_path_for_processing = target_pdf_path
                        pdf_filename = f"{base_name}.pdf"
                        yield {'message': f'✓ Image ready as PDF {pdf_filename}', 'document_number': i, 'total_documents': len(single_docs)}
                    else:
                        pdf_path_for_processing = analysis.file_path
                        pdf_filename = filename
                    
                    # Step 1: Insert document first with basic info (no OCR yet)
                    cursor.execute("""
                        INSERT INTO single_documents (
                            batch_id, original_filename, original_pdf_path,
                            page_count, file_size_bytes, status
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        batch_id, pdf_filename, pdf_path_for_processing,
                        analysis.page_count, int(analysis.file_size_mb * 1024 * 1024),
                        "processing"
                    ))
                    doc_id = cursor.lastrowid
                    conn.commit()  # Commit immediately to save progress
                    
                    # Step 2: Create searchable PDF with OCR (with caching)
                    searchable_pdf_path = os.path.join(searchable_dir, f"{base_name}_searchable.pdf")
                    forced_rotation = _lookup_forced_rotation(os.path.basename(pdf_filename))
                    ocr_text, ocr_confidence, ocr_status = create_searchable_pdf(
                        pdf_path_for_processing, searchable_pdf_path, doc_id, forced_rotation=forced_rotation
                    )
                    
                    if ocr_status != "success" and not ocr_status.startswith("success"):
                        error_msg = f"Failed to create searchable PDF: {ocr_status}"
                        logging.error(f"Failed to create searchable PDF for {filename}: {ocr_status}")
                        yield {
                            'error': error_msg,
                            'filename': filename,
                            'document_number': i,
                            'total_documents': len(single_docs)
                        }
                        continue
                    
                    # Step 3: Get AI suggestions (with caching)
                    ai_category, ai_filename, ai_confidence, ai_summary = _get_ai_suggestions_for_document(
                        ocr_text, filename, analysis.page_count, analysis.file_size_mb, doc_id
                    )
                    
                    # Step 4: Update document with AI analysis results
                    cursor.execute("""
                        UPDATE single_documents SET 
                            ai_suggested_category = ?, ai_suggested_filename = ?,
                            ai_confidence = ?, ai_summary = ?, status = ?
                        WHERE id = ?
                    """, (ai_category, ai_filename, ai_confidence, ai_summary, "ready_for_manipulation", doc_id))
                    conn.commit()  # Commit AI results immediately
                    
                    total_documents_processed += 1
                    logging.info(f"✓ Processed {filename} - Category: {ai_category}, Name: {ai_filename}")
                    
                    # Signal document completion
                    yield {
                        'document_complete': True,
                        'filename': filename,
                        'category': ai_category,
                        'ai_name': ai_filename,
                        'confidence': ai_confidence,
                        'document_number': i,
                        'total_documents': len(single_docs),
                        'documents_completed': total_documents_processed
                    }
                    
                except Exception as e:
                    error_msg = f"Error processing document: {str(e)}"
                    logging.error(f"Error processing {analysis.file_path}: {e}")
                    yield {
                        'error': error_msg,
                        'filename': filename,
                        'document_number': i,
                        'total_documents': len(single_docs)
                    }
                    continue
            
            conn.commit()
            
            # Log the batch creation
            safe_log_interaction(
                batch_id=batch_id,
                document_id=None,
                user_id=get_current_user_id(),
                event_type="single_documents_batch_created",
                step="smart_processing",
                content=json.dumps({
                    "documents_processed": total_documents_processed,
                    "workflow": "improved_single_document_with_progress",
                    "status": "ready_for_manipulation"
                }),
                notes=f"Improved single document workflow with progress - {total_documents_processed} documents ready"
            )
            
            # Update batch status to ready_for_manipulation now that processing is complete
            cursor.execute(
                "UPDATE batches SET status = ? WHERE id = ?",
                (app_config.STATUS_READY_FOR_MANIPULATION, batch_id)
            )
            conn.commit()
            
            logging.info(f"✓ Successfully created batch {batch_id} with {total_documents_processed} documents ready for manipulation")
            
    except Exception as e:
        logging.error(f"Error creating single documents batch: {e}")
        yield {
            'error': f"Batch creation failed: {str(e)}",
            'filename': None,
            'document_number': 0,
            'total_documents': len(single_docs)
        }


def _process_docs_into_fixed_batch_with_progress(docs: List[DocumentAnalysis], batch_id: int):
    """Process DocumentAnalysis list into an already-created batch id.

    Mirrors _process_single_documents_as_batch_with_progress but reuses supplied batch_id
    (never creating or selecting a different batch). Yields the same kinds of progress
    dictionaries plus an initial {'batch_id': batch_id} indicator.
    """
    if not docs:
        return
    logging.info(f"Processing {len(docs)} documents into fixed batch {batch_id}...")
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            yield {'batch_id': batch_id}
            batch_dir = os.path.join(app_config.PROCESSED_DIR, str(batch_id))
            searchable_dir = os.path.join(batch_dir, "searchable_pdfs")
            os.makedirs(searchable_dir, exist_ok=True)
            total_documents_processed = 0
            for i, analysis in enumerate(docs, 1):
                filename = os.path.basename(analysis.file_path)
                base_name = os.path.splitext(filename)[0]
                try:
                    yield {'document_start': True, 'filename': filename, 'document_number': i, 'total_documents': len(docs)}
                    if is_image_file(analysis.file_path):
                        batch_wip_dir = os.path.join(app_config.WIP_DIR, str(batch_id))
                        original_pdfs_dir = os.path.join(batch_wip_dir, "original_pdfs")
                        os.makedirs(original_pdfs_dir, exist_ok=True)
                        normalized_pdf_candidate = getattr(analysis, 'pdf_path', None)
                        target_pdf_path = os.path.join(original_pdfs_dir, f"{base_name}.pdf")
                        if normalized_pdf_candidate and normalized_pdf_candidate.lower().endswith('.pdf') and os.path.exists(normalized_pdf_candidate):
                            yield {'message': f'Reusing normalized image PDF {filename}...', 'document_number': i, 'total_documents': len(docs)}
                            try:
                                if normalized_pdf_candidate != target_pdf_path:
                                    if os.path.exists(target_pdf_path) and _files_identical(normalized_pdf_candidate, target_pdf_path):
                                        logging.info(f"♻ Skipping copy (identical) normalized PDF for image {filename}")
                                    else:
                                        import shutil
                                        shutil.copy2(normalized_pdf_candidate, target_pdf_path)
                                logging.info(f"♻ Reused normalized PDF for image {filename}")
                            except Exception as reuse_e:
                                logging.warning(f"Reuse failed for {filename}: {reuse_e}; converting freshly")
                                convert_image_to_pdf(analysis.file_path, target_pdf_path)
                        else:
                            yield {'message': f'Converting image {filename} to PDF...', 'document_number': i, 'total_documents': len(docs)}
                            convert_image_to_pdf(analysis.file_path, target_pdf_path)
                        # Archive original image once
                        try:
                            archive_dir = os.path.join(app_config.ARCHIVE_DIR, f"batch_{batch_id}_images")
                            os.makedirs(archive_dir, exist_ok=True)
                            archived_image_path = os.path.join(archive_dir, filename)
                            if os.path.exists(analysis.file_path):
                                safe_move(analysis.file_path, archived_image_path)
                        except Exception as arch_e:
                            logging.warning(f"Archiving original image failed for {filename}: {arch_e}")
                        pdf_path_for_processing = target_pdf_path
                        pdf_filename = f"{base_name}.pdf"
                        yield {'message': f'✓ Image ready as PDF {pdf_filename}', 'document_number': i, 'total_documents': len(docs)}
                    else:
                        pdf_path_for_processing = analysis.file_path
                        pdf_filename = filename
                    cursor.execute("""
                        INSERT INTO single_documents (
                            batch_id, original_filename, original_pdf_path,
                            page_count, file_size_bytes, status
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        batch_id, pdf_filename, pdf_path_for_processing,
                        analysis.page_count, int(analysis.file_size_mb * 1024 * 1024),
                        "processing"
                    ))
                    doc_id = cursor.lastrowid
                    conn.commit()
                    searchable_pdf_path = os.path.join(searchable_dir, f"{base_name}_searchable.pdf")
                    forced_rotation = _lookup_forced_rotation(os.path.basename(pdf_filename))
                    ocr_text, ocr_confidence, ocr_status = create_searchable_pdf(
                        pdf_path_for_processing, searchable_pdf_path, doc_id, forced_rotation=forced_rotation
                    )
                    if ocr_status != "success" and not ocr_status.startswith("success"):
                        yield {'error': f'Failed to create searchable PDF: {ocr_status}', 'filename': filename, 'document_number': i, 'total_documents': len(docs)}
                        continue
                    ai_category, ai_filename, ai_confidence, ai_summary = _get_ai_suggestions_for_document(
                        ocr_text, filename, analysis.page_count, analysis.file_size_mb, doc_id
                    )
                    cursor.execute("""
                        UPDATE single_documents SET 
                            ai_suggested_category = ?, ai_suggested_filename = ?,
                            ai_confidence = ?, ai_summary = ?, status = ?
                        WHERE id = ?
                    """, (ai_category, ai_filename, ai_confidence, ai_summary, "ready_for_manipulation", doc_id))
                    conn.commit()
                    total_documents_processed += 1
                    yield {
                        'document_complete': True,
                        'filename': filename,
                        'category': ai_category,
                        'ai_name': ai_filename,
                        'confidence': ai_confidence,
                        'document_number': i,
                        'total_documents': len(docs),
                        'documents_completed': total_documents_processed
                    }
                except Exception as e:
                    logging.error(f"Error processing {analysis.file_path}: {e}")
                    yield {'error': f'Error processing document: {e}', 'filename': filename, 'document_number': i, 'total_documents': len(docs)}
                    continue
            conn.commit()
            safe_log_interaction(
                batch_id=batch_id,
                document_id=None,
                user_id=get_current_user_id(),
                event_type="single_documents_batch_created",
                step="smart_processing",
                content=json.dumps({
                    "documents_processed": total_documents_processed,
                    "workflow": "fixed_batch_single_document",
                    "status": "ready_for_manipulation"
                }),
                notes=f"Fixed batch workflow - {total_documents_processed} documents ready"
            )
            cursor.execute("UPDATE batches SET status = ? WHERE id = ?", (app_config.STATUS_READY_FOR_MANIPULATION, batch_id))
            conn.commit()
            logging.info(f"✓ Fixed batch {batch_id} processed {total_documents_processed} documents")
    except Exception as e:
        logging.error(f"Error in fixed batch processing: {e}")
        yield {'error': f'Fixed batch processing failed: {e}', 'filename': None, 'document_number': 0, 'total_documents': len(docs)}

def cleanup_empty_batch_directory(batch_id: int) -> bool:
    """
    Clean up empty batch directories after processing is complete.
    
    This function safely removes empty batch directories and their subdirectories
    from the processed directory (WIP) after a batch has been exported/completed.
    
    Args:
        batch_id (int): The batch ID to clean up
        
    Returns:
        bool: True if cleanup was successful or not needed, False if error occurred
    """
    try:
        batch_dir = os.path.join(app_config.PROCESSED_DIR, str(batch_id))
        
        if not os.path.exists(batch_dir):
            logging.debug(f"Batch directory {batch_dir} doesn't exist - no cleanup needed")
            return True
            
        logging.info(f"Checking for cleanup of batch directory: {batch_dir}")
        
        # Check if directory and all subdirectories are empty
        def is_directory_empty_recursive(path):
            """Check if directory and all subdirectories are empty."""
            try:
                if not os.path.isdir(path):
                    return False
                    
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    if os.path.isfile(item_path):
                        return False  # Found a file
                    elif os.path.isdir(item_path):
                        if not is_directory_empty_recursive(item_path):
                            return False  # Subdirectory is not empty
                return True
            except Exception:
                return False
        
        if is_directory_empty_recursive(batch_dir):
            # Safe to remove - directory and all subdirectories are empty
            import shutil
            shutil.rmtree(batch_dir)
            logging.info(f"✓ Cleaned up empty batch directory: {batch_dir}")
            return True
        else:
            # Directory contains files - don't remove
            files_found = []
            for root, dirs, files in os.walk(batch_dir):
                for file in files:
                    files_found.append(os.path.relpath(os.path.join(root, file), batch_dir))
            
            logging.info(f"⚠️  Batch directory {batch_dir} not empty - keeping it")
            logging.debug(f"  Files found: {files_found[:5]}{'...' if len(files_found) > 5 else ''}")
            return True
            
    except Exception as e:
        logging.error(f"Error during batch directory cleanup for batch {batch_id}: {e}")
        return False


def cleanup_batch_on_completion(batch_id: int, completion_type: str = "export") -> bool:
    """
    Perform cleanup operations when a batch is completed.
    
    Args:
        batch_id (int): The batch ID that was completed
        completion_type (str): Type of completion ('export', 'finalize', etc.)
        
    Returns:
        bool: True if cleanup was successful
    """
    try:
        logging.info(f"Starting batch completion cleanup for batch {batch_id} ({completion_type})")
        
        # Clean up empty directories
        cleanup_success = cleanup_empty_batch_directory(batch_id)
        
        # Log cleanup action for audit trail
        log_interaction(
            batch_id=batch_id,
            document_id=None,
            user_id=get_current_user_id(),
            event_type="batch_cleanup",
            step="completion",
            content=f"Cleanup performed after {completion_type}",
            notes=f"Directory cleanup: {'success' if cleanup_success else 'failed'}"
        )
        
        return cleanup_success
        
    except Exception as e:
        logging.error(f"Error in batch completion cleanup: {e}")
        return False


def _detect_best_rotation(image_path: str) -> tuple[int, float, str]:
    """
    Automatically detect the best rotation for an image by testing OCR confidence at different rotations.
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        tuple: (best_rotation_angle, confidence_score, ocr_text)
    """
    if not os.path.exists(image_path):
        logging.warning(f"Image not found for rotation detection: {image_path}")
        return 0, 0.0, ""
        
    try:
        from PIL import Image
        import numpy as np
        
        # Test rotations: 0, 90, 180, 270 degrees
        rotations_to_test = [0, 90, 180, 270]
        best_rotation = 0
        best_confidence = 0.0
        best_text = ""
        results = {}
        
        with Image.open(image_path) as img:
            reader = EasyOCRSingleton.get_reader()
            
            for rotation in rotations_to_test:
                try:
                    # Rotate image for testing
                    if rotation == 0:
                        test_img = img
                    else:
                        test_img = img.rotate(-rotation, expand=True)
                    
                    # Run OCR and get results with confidence scores
                    ocr_results = reader.readtext(np.array(test_img))
                    
                    if ocr_results:
                        # Calculate average confidence and extract text
                        confidences = [conf for (_, _, conf) in ocr_results]
                        # Compute average with explicit float conversion for static analyzers
                        # Defensive cast to int for static analysis (ensure Iterable[int])
                        if confidences:
                            int_conf_list: list[int] = [int(x) for x in confidences]
                            avg_confidence = sum(int_conf_list) / len(int_conf_list)
                        else:
                            avg_confidence = 0.0
                        text = " ".join([text for (_, text, _) in ocr_results])
                        
                        # Additional heuristics for better detection
                        text_length = len(text.strip())
                        word_count = len(text.split())
                        
                        # Boost score for longer, more readable text
                        adjusted_confidence = avg_confidence
                        if text_length > 50:  # Reasonable amount of text
                            adjusted_confidence *= 1.1
                        if word_count > 10:  # Good word count
                            adjusted_confidence *= 1.05
                            
                        results[rotation] = {
                            'confidence': adjusted_confidence,
                            'text': text,
                            'raw_confidence': avg_confidence,
                            'text_length': text_length
                        }
                        
                        logging.debug(f"Rotation {rotation}°: confidence={avg_confidence:.3f}, adjusted={adjusted_confidence:.3f}, text_len={text_length}")
                        
                        if adjusted_confidence > best_confidence:
                            best_confidence = adjusted_confidence
                            best_rotation = rotation
                            best_text = text
                    else:
                        results[rotation] = {'confidence': 0.0, 'text': '', 'raw_confidence': 0.0, 'text_length': 0}
                        
                except Exception as rotation_error:
                    logging.warning(f"Failed to test rotation {rotation}°: {rotation_error}")
                    results[rotation] = {'confidence': 0.0, 'text': '', 'raw_confidence': 0.0, 'text_length': 0}
        
        # Log results for debugging
        logging.info(f"Rotation detection results for {os.path.basename(image_path)}:")
        for rot, res in results.items():
            logging.info(f"  {rot}°: confidence={res['raw_confidence']:.3f}, text_length={res['text_length']}")
        logging.info(f"  → Best rotation: {best_rotation}° (confidence: {best_confidence:.3f})")
        
        return best_rotation, best_confidence, best_text
        
    except Exception as e:
        logging.error(f"Error in rotation detection: {e}")
        return 0, 0.0, ""


def _get_ai_suggestions_for_document(ocr_text: str, filename: str, page_count: int, 
                                   file_size_mb: float, document_id: Optional[int] = None) -> tuple[str, str, float, str]:
    """
    Get AI suggestions for document category, filename, and summary.
    
    First checks database cache, only makes LLM calls if needed.
    
    Args:
        ocr_text: Extracted OCR text from the document
        filename: Original filename
        page_count: Number of pages in the document
        file_size_mb: File size in megabytes
        document_id: Optional document ID to check for cached results
        
    Returns:
        tuple: (category, suggested_filename, confidence, summary)
    """
    try:
        # Check cache first if document_id provided
        if document_id:
            with database_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT ai_suggested_category, ai_suggested_filename, ai_confidence, ai_summary 
                    FROM single_documents 
                    WHERE id = ? AND ai_suggested_category IS NOT NULL
                """, (document_id,))
                cached_result = cursor.fetchone()
                
                if cached_result:
                    category, suggested_filename, confidence, summary = cached_result
                    logging.info(f"✅ Using cached AI analysis for document {document_id}: {category}")
                    return category, suggested_filename, confidence or 0.8, summary or ""
        
        # No cache found, proceed with LLM analysis
        logging.info(f"🤖 Generating new AI analysis for document: {filename}")
        
        # Get available categories from database
        with database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM categories ORDER BY name")
            categories = [row[0] for row in cursor.fetchall()]
        
        if not categories:
            categories = ["Uncategorized"]
        
        # Prepare prompt for AI classification
        categories_text = ", ".join(categories)
        
        # Truncate OCR text if too long (keep first 2000 characters)
        ocr_sample = ocr_text[:2000] if len(ocr_text) > 2000 else ocr_text
        
        prompt = f"""Document Classification and Naming Analysis

Document Info:
- Original filename: {filename}
- Pages: {page_count}
- Size: {file_size_mb:.1f} MB
- OCR Text Sample: {ocr_sample}

Available Categories: {categories_text}

Please analyze this document and provide:
1. Best matching category from the available list
2. A descriptive filename (without extension, suitable for filing)
3. A brief summary of the document content
4. Your confidence level (0.0-1.0)

Respond in this exact JSON format:
{{
    "category": "selected_category_name",
    "filename": "descriptive_filename_without_extension",
    "summary": "brief description of document content",
    "confidence": 0.85
}}"""

        # Get AI response using direct Ollama query for JSON response
        response = _query_ollama(prompt, 
                                context_window=app_config.OLLAMA_CTX_CLASSIFICATION, 
                                task_name="document_analysis")
        
        # Parse JSON response
        if response:
            import json
            try:
                # Clean up response - remove any extra text before/after JSON
                response_clean = response.strip()
                if '{' in response_clean and '}' in response_clean:
                    # Extract JSON from response
                    start = response_clean.find('{')
                    end = response_clean.rfind('}') + 1
                    json_str = response_clean[start:end]
                    
                    parsed = json.loads(json_str)
                    
                    # Validate that suggested filename is different from original
                    ai_filename = parsed.get("filename", "").strip()
                    original_base = filename.replace(".pdf", "").replace(".PDF", "")
                    
                    # If AI didn't provide a meaningful filename, create one based on content
                    if not ai_filename or ai_filename == original_base:
                        # Generate filename based on category and content
                        category = parsed.get("category", "Document")
                        summary = parsed.get("summary", "")[:50]  # First 50 chars of summary
                        if summary:
                            # Create filename from category and summary
                            ai_filename = f"{category}_{summary}".replace(" ", "_").replace(",", "").replace(".", "")[:50]
                        else:
                            ai_filename = f"{category}_Document"
                    
                    result = (
                        parsed.get("category", "Uncategorized"),
                        ai_filename,
                        float(parsed.get("confidence", 0.5)),
                        parsed.get("summary", "AI analysis completed")
                    )
                    
                    # Save to database cache if document_id provided
                    if document_id:
                        try:
                            with database_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE single_documents SET 
                                        ai_suggested_category = ?, ai_suggested_filename = ?,
                                        ai_confidence = ?, ai_summary = ?
                                    WHERE id = ?
                                """, (result[0], result[1], result[2], result[3], document_id))
                                conn.commit()
                                logging.info(f"💾 Cached AI analysis for document {document_id}")
                        except Exception as cache_error:
                            logging.warning(f"Failed to cache AI analysis: {cache_error}")
                    
                    return result
                    
            except Exception as e:
                logging.warning(f"Failed to parse AI response as JSON: {e}")
                logging.debug(f"Response was: {response}")
                
        # Fallback if AI response fails
        return (
            "Uncategorized",
            filename.replace(".pdf", ""),
            0.3,
            "AI classification failed - manual review needed"
        )
            
    except Exception as e:
        logging.error(f"Error getting AI suggestions: {e}")
        return (
            "Uncategorized", 
            filename.replace(".pdf", ""),
            0.1,
            f"Error during AI analysis: {str(e)}"
        )





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
                sanitized_filename = sanitize_filename(filename)

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
                
                # Archive the original file - ONLY after successful processing
                try:
                    archive_path = os.path.join(app_config.ARCHIVE_DIR, filename)
                    safe_move(file_path, archive_path)
                    logging.info(f"✓ Archived original to {archive_path}")
                except OSError as move_e:
                    logging.error(f"✗ CRITICAL: Failed to archive {filename}: {move_e}")
                    logging.error(f"✗ Original file remains in intake: {file_path}")
                    # DO NOT DELETE the original - leave it in intake for manual handling

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

PAGE TEXT:
{page_text[:3000]}
END PAGE TEXT:
"""
    result = _query_ollama(prompt, timeout=30, context_window=app_config.OLLAMA_CTX_ORDERING, task_name="ordering")
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
        # If page is a sqlite3.Row, convert to dict for .get() access
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
You are a file naming expert. Create a descriptive filename using ONLY these characters:
- Letters (a-z, A-Z)  
- Numbers (0-9)
- Underscores (_)

REQUIRED FORMAT: Use_Underscores_Between_Words
GOOD: loan_settlement_statement_mccaleb
BAD: loan-settlement-statement-mccaleb  
BAD: LoanSettlementStatementMcCaleb
BAD: loan settlement statement mccaleb

Your response must be ONLY the filename with underscores.

DOCUMENT TEXT (Category: '{category}'):
{document_text[:6000]}
"""
    ai_title = _query_ollama(prompt, timeout=90, context_window=app_config.OLLAMA_CTX_TITLE_GENERATION, task_name="title_generation")
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
    # Remove common conversational prefixes more comprehensively
    ai_title = re.sub(r'^\s*(Here\s+is.*?:\s*|Based\s+on.*?:\s*|A\s+good.*?:\s*)', '', ai_title, flags=re.IGNORECASE)
    
    # Convert spaces and hyphens to underscores for consistency with security.sanitize_filename()
    ai_title = re.sub(r'[\s\-]+', '_', ai_title)  # Convert whitespace and hyphens to underscores
    # Remove any characters that are not alphanumeric or underscore
    sanitized_title = re.sub(r'[^\w_]', '', ai_title).strip('_')

    if not sanitized_title:
        sanitized_title = "Untitled_Document"

    return f"{current_date}_{sanitized_title}"


def export_document(
    pages: List[Dict], final_name_base: str, category: str, document_id: Optional[int] = None
) -> bool:
    """Exports a final document to the filing cabinet in multiple formats:
    1. A standard, multi-page PDF from the images.
    2. A searchable, multi-page PDF with the OCR text embedded.
    3. A Markdown file containing the full OCR text and metadata."""
    
    # Sanitize inputs for filesystem safety and consistency
    final_name_base = sanitize_filename(final_name_base)
    
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

        # --- 3. Markdown Log File with Optional Tag Extraction ---
        markdown_path = os.path.join(destination_dir, f"{final_name_base}_log.md")
        
        # Extract tags using LLM if enabled
        extracted_tags = None
        if app_config.ENABLE_TAG_EXTRACTION:
            try:
                logging.info(f"🏷️  Starting tag extraction for document: {final_name_base}")
                extracted_tags = extract_document_tags(full_ocr_text, final_name_base)
                if extracted_tags:
                    total_tags = sum(len(tag_list) for tag_list in extracted_tags.values())
                    logging.info(f"✅ Tag extraction SUCCESS: {total_tags} tags extracted for {final_name_base}")
                    logging.debug(f"🏷️  Tag breakdown: {[(cat, len(tags)) for cat, tags in extracted_tags.items() if tags]}")
                    
                    # Store tags in database if document_id is provided
                    if document_id:
                        try:
                            tags_stored = store_document_tags(document_id, extracted_tags)
                            logging.info(f"🏷️  Stored {tags_stored} tags in database for document {document_id}")
                        except Exception as db_e:
                            logging.error(f"💥 Failed to store tags in database for document {document_id}: {db_e}")
                    else:
                        logging.debug(f"🏷️  No document_id provided - tags stored in markdown only")
                else:
                    logging.warning(f"⚠️  Tag extraction returned no results for {final_name_base}")
            except Exception as e:
                logging.error(f"💥 Tag extraction FAILED for {final_name_base}: {e}")
                extracted_tags = None
        else:
            logging.debug(f"🏷️  Tag extraction DISABLED by configuration for {final_name_base}")
        
        log_content = f"""# Document Export Log

- **Final Filename**: `{final_name_base}`
- **Category**: `{category}`
- **Export Timestamp**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
- **Total Pages**: {len(pages)}
"""

        # Add extracted tags section if available
        if extracted_tags:
            log_content += "\n## Extracted Tags\n\n"
            
            for tag_category, tag_list in extracted_tags.items():
                if tag_list:  # Only include categories that have tags
                    category_name = tag_category.replace('_', ' ').title()
                    log_content += f"**{category_name}**: {', '.join(tag_list)}\n\n"
            
            # Add a summary for quick reference
            all_tags = []
            for tag_list in extracted_tags.values():
                all_tags.extend(tag_list)
            
            if all_tags:
                log_content += f"**All Tags** ({len(all_tags)} total): {', '.join(all_tags)}\n\n"

        log_content += """## Processing Metadata

| Page ID | Source File         | Original Page # | AI Suggestion                 |
|---------|---------------------|-----------------|-------------------------------|
"""
        for p in pages:
            # If p is a sqlite3.Row, convert to dict for .get() access
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


def finalize_single_documents_batch(batch_id: int) -> bool:
    """
    Finalize and export all single documents in a batch:
    - Move original PDF, searchable PDF, and markdown to correct category folder
    - Only move files after all outputs are created
    - Never delete or lose source files, even on error/interruption
    """
    from doc_processor.database import get_db_connection
    import shutil
    success = True
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, original_pdf_path, searchable_pdf_path, final_category, final_filename, ai_suggested_category, ai_suggested_filename, ocr_text FROM single_documents WHERE batch_id=?", (batch_id,))
    docs = cursor.fetchall()
    for doc in docs:
        doc_id = doc[0]
        original_pdf = doc[1]
        searchable_pdf = doc[2]
        # Use final category/filename if available, otherwise fall back to AI suggestions
        category = doc[3] or doc[5] or "Uncategorized"
        filename_base = doc[4] or doc[6] or f"document_{doc_id}"
        # Sanitize filename for filesystem safety and consistency
        filename_base = sanitize_filename(filename_base)
        ocr_text = doc[7] or ""
        # Destination folder - sanitize category name for consistency with single export
        category_dir_name = _sanitize_category(category)
        category_dir = os.path.join(app_config.FILING_CABINET_DIR, category_dir_name)
        os.makedirs(category_dir, exist_ok=True)
        # Prepare all destination paths
        dest_original = os.path.join(category_dir, f"{filename_base}_original.pdf")
        dest_searchable = os.path.join(category_dir, f"{filename_base}_searchable.pdf")
        dest_markdown = os.path.join(category_dir, f"{filename_base}.md")
        
        # Create markdown file with tag extraction
        try:
            # Extract tags if enabled
            extracted_tags = None
            if app_config.ENABLE_TAG_EXTRACTION and ocr_text:
                try:
                    logging.info(f"🏷️  Starting tag extraction for single document: {filename_base}")
                    extracted_tags = extract_document_tags(ocr_text, filename_base)
                    if extracted_tags:
                        total_tags = sum(len(tag_list) for tag_list in extracted_tags.values())
                        logging.info(f"✅ Tag extraction SUCCESS: {total_tags} tags extracted for {filename_base}")
                        
                        # Store tags in database
                        try:
                            tags_stored = store_document_tags(doc_id, extracted_tags)
                            logging.info(f"🏷️  Stored {tags_stored} tags in database for single document {doc_id}")
                        except Exception as db_e:
                            logging.error(f"💥 Failed to store tags in database for single document {doc_id}: {db_e}")
                    else:
                        logging.warning(f"⚠️  Tag extraction returned no results for {filename_base}")
                except Exception as e:
                    logging.error(f"💥 Tag extraction FAILED for {filename_base}: {e}")
                    extracted_tags = None
            
            # Create enhanced markdown content
            markdown_content = f"# {filename_base}\n\n**Category:** {category}\n\n"
            
            # Add extracted tags section if available
            if extracted_tags:
                markdown_content += "## Extracted Tags\n\n"
                
                for tag_category, tag_list in extracted_tags.items():
                    if tag_list:  # Only include categories that have tags
                        category_name = tag_category.replace('_', ' ').title()
                        markdown_content += f"**{category_name}**: {', '.join(tag_list)}\n\n"
                
                # Add a summary for quick reference
                all_tags = []
                for tag_list in extracted_tags.values():
                    all_tags.extend(tag_list)
                
                if all_tags:
                    markdown_content += f"**All Tags** ({len(all_tags)} total): {', '.join(all_tags)}\n\n"
            
            markdown_content += f"## OCR Content\n\n{ocr_text}"
            
            with open(dest_markdown, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            logging.debug(f"✓ Created enhanced markdown with tags: {dest_markdown}")
        except Exception as e:
            logging.error(f"Failed to create markdown for doc {doc_id}: {e}")
            success = False
            continue  # Skip this document if we can't create outputs
        
        # Move files ONLY after all outputs are successfully created
        files_moved = []
        try:
            # Move original PDF
            if os.path.exists(original_pdf):
                safe_move(original_pdf, dest_original)
                files_moved.append(dest_original)
                logging.debug(f"✓ Moved original: {dest_original}")
            
            # Move searchable PDF
            if os.path.exists(searchable_pdf):
                safe_move(searchable_pdf, dest_searchable)
                files_moved.append(dest_searchable)
                logging.debug(f"✓ Moved searchable: {dest_searchable}")
                
            logging.info(f"✅ Successfully exported document {doc_id} to {category_dir}")
            
        except Exception as e:
            logging.error(f"💥 CRITICAL: Failed to move files for doc {doc_id}: {e}")
            logging.error(f"💥 Rolling back moved files: {files_moved}")
            
            # ROLLBACK: Move any successfully moved files back to prevent loss
            for moved_file in files_moved:
                try:
                    if "original" in moved_file and os.path.exists(moved_file):
                        safe_move(moved_file, original_pdf)
                        logging.info(f"🔄 Rolled back original to: {original_pdf}")
                    elif "searchable" in moved_file and os.path.exists(moved_file):
                        safe_move(moved_file, searchable_pdf)
                        logging.info(f"🔄 Rolled back searchable to: {searchable_pdf}")
                except Exception as rollback_e:
                    logging.error(f"💥 ROLLBACK FAILED: {rollback_e}")
            
            success = False
    
    conn.close()
    
    if success:
        logging.info(f"✅ All single documents in batch {batch_id} exported successfully")
        
        # Clean up the batch directory in WIP after successful export
        try:
            cleanup_success = cleanup_batch_files(batch_id)
            if cleanup_success:
                logging.info(f"✅ Successfully cleaned up batch {batch_id} directory")
            else:
                logging.warning(f"⚠️ Export succeeded but failed to clean up batch {batch_id} directory")
        except Exception as cleanup_e:
            logging.error(f"💥 Failed to clean up batch {batch_id} directory: {cleanup_e}")
    else:
        logging.warning(f"⚠️ Some documents in batch {batch_id} failed export - check logs above")
    
    return success


def verify_no_file_loss() -> dict:
    """
    Verify that no PDF files have been lost during processing.
    Returns a report of file locations and safety status.
    """
    report = {
        "intake_files": [],
        "archive_files": [],
        "filing_cabinet_files": [],
        "potential_losses": [],
        "status": "safe"
    }
    
    try:
        # Check intake directory
        if os.path.exists(app_config.INTAKE_DIR):
            intake_pdfs = [f for f in os.listdir(app_config.INTAKE_DIR) if f.lower().endswith('.pdf')]
            report["intake_files"] = intake_pdfs
        
        # Check archive directory
        if os.path.exists(app_config.ARCHIVE_DIR):
            archive_pdfs = [f for f in os.listdir(app_config.ARCHIVE_DIR) if f.lower().endswith('.pdf')]
            report["archive_files"] = archive_pdfs
        
        # Check filing cabinet (recursively)
        if os.path.exists(app_config.FILING_CABINET_DIR):
            filing_pdfs = []
            for root, dirs, files in os.walk(app_config.FILING_CABINET_DIR):
                for file in files:
                    if file.lower().endswith('.pdf'):
                        filing_pdfs.append(os.path.relpath(os.path.join(root, file), app_config.FILING_CABINET_DIR))
            report["filing_cabinet_files"] = filing_pdfs
        
        # Log summary
        total_files = len(report["intake_files"]) + len(report["archive_files"]) + len(report["filing_cabinet_files"])
        logging.info(f"📊 File safety check: {total_files} PDFs found across all directories")
        logging.info(f"📁 Intake: {len(report['intake_files'])}, Archive: {len(report['archive_files'])}, Filing Cabinet: {len(report['filing_cabinet_files'])}")
        
    except Exception as e:
        report["status"] = "error"
        report["error"] = str(e)
        logging.error(f"File safety check failed: {e}")
    
    return report


def finalize_single_documents_batch_with_progress(batch_id: int, progress_callback=None) -> bool:
    """
    Finalize and export all single documents in a batch with progress tracking.
    
    Args:
        batch_id: The batch ID to export
        progress_callback: Function to call with progress updates (current, total, message, details)
    
    Returns:
        bool: True if successful, False otherwise
    """
    def update_progress(current, total, message, details=""):
        if progress_callback:
            progress_callback(current, total, message, details)
    
    success = True
    from .database import get_db_connection as _get_db_conn
    conn = _get_db_conn()
    cursor = conn.cursor()
    
    # Get all documents
    cursor.execute("SELECT id, original_pdf_path, searchable_pdf_path, final_category, final_filename, ai_suggested_category, ai_suggested_filename, ocr_text FROM single_documents WHERE batch_id=?", (batch_id,))
    docs = cursor.fetchall()
    
    total_docs = len(docs)
    update_progress(0, total_docs, "Starting export process...", "Preparing to export documents")
    
    for i, doc in enumerate(docs):
        doc_id = doc[0]
        original_pdf = doc[1]
        searchable_pdf = doc[2]
        
        # Use final category/filename if available, otherwise fall back to AI suggestions
        category = doc[3] or doc[5] or "Uncategorized"
        filename_base = doc[4] or doc[6] or f"document_{doc_id}"
        
        update_progress(i, total_docs, f"Exporting: {filename_base}", f"Processing document {i+1} of {total_docs}")
        
        # Sanitize filename for filesystem safety and consistency
        filename_base = sanitize_filename(filename_base)
        ocr_text = doc[7] or ""
        
        # Destination folder - sanitize category name
        category_dir_name = _sanitize_category(category)
        category_dir = os.path.join(app_config.FILING_CABINET_DIR, category_dir_name)
        os.makedirs(category_dir, exist_ok=True)
        
        # Prepare all destination paths
        dest_original = os.path.join(category_dir, f"{filename_base}_original.pdf")
        dest_searchable = os.path.join(category_dir, f"{filename_base}_searchable.pdf")
        dest_markdown = os.path.join(category_dir, f"{filename_base}.md")
        
        try:
            # Extract tags if enabled
            extracted_tags = None
            if app_config.ENABLE_TAG_EXTRACTION and ocr_text:
                update_progress(i, total_docs, f"Extracting tags: {filename_base}", "Analyzing document content for tags")
                try:
                    logging.info(f"🏷️  Starting tag extraction for single document: {filename_base}")
                    extracted_tags = extract_document_tags(ocr_text, filename_base)
                    if extracted_tags:
                        total_tags = sum(len(tag_list) for tag_list in extracted_tags.values())
                        logging.info(f"✅ Tag extraction SUCCESS: {total_tags} tags extracted for {filename_base}")
                        
                        # Store tags in database
                        try:
                            tags_stored = store_document_tags(doc_id, extracted_tags)
                            logging.info(f"🏷️  Stored {tags_stored} tags in database for single document {doc_id}")
                        except Exception as db_e:
                            logging.error(f"💥 Failed to store tags in database for single document {doc_id}: {db_e}")
                    else:
                        logging.warning(f"⚠️  Tag extraction returned no results for {filename_base}")
                except Exception as tag_e:
                    logging.error(f"💥 Tag extraction FAILED for {filename_base}: {tag_e}")
                    extracted_tags = None
            
            update_progress(i, total_docs, f"Creating markdown: {filename_base}", "Generating markdown file")
            
            # Create enhanced markdown content
            markdown_content = _create_single_document_markdown_content(
                original_filename=filename_base,
                category=category,
                ocr_text=ocr_text,
                extracted_tags=extracted_tags
            )
            
            # Write markdown file
            with open(dest_markdown, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            update_progress(i, total_docs, f"Copying files: {filename_base}", "Moving PDF files to category folder")
            
            # Copy files (don't move original files, copy them for safety)
            if original_pdf and os.path.exists(original_pdf):
                shutil.copy2(original_pdf, dest_original)
                logging.info(f"📄 Copied original PDF: {original_pdf} → {dest_original}")
            
            if searchable_pdf and os.path.exists(searchable_pdf):
                shutil.copy2(searchable_pdf, dest_searchable)
                logging.info(f"📄 Copied searchable PDF: {searchable_pdf} → {dest_searchable}")
            
            logging.info(f"✅ Successfully exported document {doc_id} to {category_dir}")
            
        except Exception as e:
            logging.error(f"❌ Failed to export single document {doc_id} ({filename_base}): {e}")
            success = False
            continue
    
    # Final progress update
    if success:
        update_progress(total_docs, total_docs, "Cleaning up batch files...", "Removing temporary batch directory")
        
        # Clean up the batch directory in WIP after successful export
        try:
            cleanup_success = cleanup_batch_files(batch_id)
            if cleanup_success:
                logging.info(f"✅ Successfully cleaned up batch {batch_id} directory")
                update_progress(total_docs, total_docs, "Export completed successfully!", f"All {total_docs} documents exported and batch directory cleaned up")
            else:
                logging.warning(f"⚠️ Export succeeded but failed to clean up batch {batch_id} directory")
                update_progress(total_docs, total_docs, "Export completed successfully!", f"All {total_docs} documents exported (manual cleanup may be needed)")
        except Exception as cleanup_e:
            logging.error(f"💥 Failed to clean up batch {batch_id} directory: {cleanup_e}")
            update_progress(total_docs, total_docs, "Export completed successfully!", f"All {total_docs} documents exported (cleanup failed)")
    else:
        update_progress(total_docs, total_docs, "Export completed with some errors", "Check logs for details")
    
    conn.close()
    return success


def _create_single_document_markdown_content(original_filename, category, ocr_text, extracted_tags=None):
    """Create enhanced markdown content for a single document."""
    import datetime
    
    # Start with basic metadata
    content = f"""# {original_filename}

**Category:** {category}  
**Export Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""
    
    # Add tags section if available
    if extracted_tags:
        content += "## 🏷️ Extracted Tags\n\n"
        for tag_type, tags in extracted_tags.items():
            if tags:
                content += f"**{tag_type.title()}:** {', '.join(tags)}  \n"
        content += "\n"
    
    # Add OCR content
    content += "## 📄 Document Content\n\n"
    if ocr_text:
        content += f"```\n{ocr_text}\n```\n"
    else:
        content += "*No text content extracted*\n"
    
    return content
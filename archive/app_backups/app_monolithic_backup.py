"""ARCHIVED MONOLITHIC APP (READ-ONLY)

Preserved for historical reference after migration to blueprint architecture.
Original location: doc_processor/app_monolithic_backup.py
Status: DO NOT EDIT. DO NOT IMPORT IN RUNTIME.
Modern entrypoint: doc_processor/app.py

This file retained verbatim (except for this header) to allow
code archaeology and diffing during cleanup cycles.
"""

# ==== BEGIN ORIGINAL CONTENT ====
# --- ARCHIVE CLEANUP ON NEW BATCH ---

def cleanup_old_archives():  # pragma: no cover - inert in archive
	"""Stub preserved for historical context (logic removed to avoid unresolved references)."""
	pass

"""
This module is the central hub of the document processing web application.
It uses the Flask web framework to create a user interface for a multi-stage
document processing pipeline. The application is designed to guide a user
through a series of steps to take a batch of raw documents (e.g., scans)
and turn them into organized, categorized, and named files.

The pipeline consists of the following major stages, each managed by
one or more routes in this file:

1.  **Batch Processing**: A user initiates the processing of a new batch of
	documents from a predefined source directory. The `processing.py` module
	handles the heavy lifting of OCR, image conversion, and initial AI-based
	categorization.

2    page_id = request.form.get("page_id", type=int)
	batch_id = request.form.get("batch_id", type=int)
	rotation = request.form.get("rotation", 0, type=int)

	if page_id is None or batch_id is None:
		abort(400, "Page ID and Batch ID are required")

	# Validate rotation angle
	if rotation not in {0, 90, 180, 270}:
		abort(400, "Invalid rotation angle")

	# The `rerun_ocr_on_page` function in `processing.py` handles the image
	# manipulation and the call to the OCR engine.
	try:
		rerun_ocr_on_page(page_id, rotation)
	except OCRError as e:
		logging.error(f"OCR error for page {page_id}: {e}")
		abort(500, "OCR processing failed")erification**: The user manually reviews each page of the batch. They can
	correct the AI's suggested category, rotate pages, or flag pages that
	require special attention. This is the primary quality control step.

3.  **Review**: A dedicated interface to handle only the "flagged" pages. This
	allows for focused problem-solving on pages that were unclear or had
	issues during verification.

4.  **Grouping**: After all pages are verified, the user groups them into logical
	documents. For example, a 5-page document would be created by grouping five
	individual verified pages.

5.  **Ordering**: For documents with more than one page, the user can specify the
	correct page order. An AI suggestion is available to speed up this process.

6.  **Finalization & Export**: The final step where the user gives each document a
	meaningful filename (with AI suggestions) and exports them. The application
	creates final PDF files (both with and without OCR text layers) and a log
	file, organizing them into a "filing cabinet" directory structure based on
	their category.

This module ties together the database interactions (from `database.py`) and
the core processing logic (from `processing.py`) to create a cohesive user
experience.
"""
# Standard library imports
import os
import logging
from logging.handlers import RotatingFileHandler
# --- LOGGING CONFIGURATION ---
LOG_DIR = os.getenv("LOG_DIR", os.path.join(os.path.dirname(__file__), "logs"))
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# Rotating file handler: 5MB per file, keep 5 backups
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_fmt = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
file_handler.setFormatter(file_fmt)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_fmt = logging.Formatter('%(levelname)s %(name)s: %(message)s')
console_handler.setFormatter(console_fmt)

# Root logger setup
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

# Capture all uncaught exceptions
def log_uncaught_exceptions(exc_type, exc_value, exc_traceback):
	if issubclass(exc_type, KeyboardInterrupt):
		return  # Don't log keyboard interrupts
	logging.getLogger().error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

import sys
sys.excepthook = log_uncaught_exceptions
import logging

# Third-party imports

# ...remaining original monolithic content unchanged...
# ==== END ORIGINAL CONTENT ====
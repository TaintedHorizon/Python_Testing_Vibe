import os

# config.py
# This file contains configuration settings for the document processing script.
# It is now tracked by Git as it no longer contains sensitive information.
# Users should modify this file to suit their local environment.

# API URL for Google's Gemini Flash model.
# This is the endpoint to which document text will be sent for classification and title generation.
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# --- Application Settings ---
# DRY_RUN: If True, the script will simulate file operations (moving, saving)
# and LLM interactions without actually making changes to the file system or API calls.
# This is useful for testing and debugging.
# Set to False to enable full functionality.
DRY_RUN = False

# INTAKE_DIR: Directory where new, unprocessed documents are initially placed.
# Ensure this path is absolute and accessible by the script.
INTAKE_DIR = "/mnt/scans_intake"

# PROCESSED_DIR: The base directory where all processed and categorized documents
# will be moved. Subdirectories for each category will be created here.
# Ensure this path is absolute and accessible by the script.
PROCESSED_DIR = "/mnt/scans_processed"

# CATEGORIES: A dictionary mapping document categories to their respective subdirectories.
# The script will attempt to classify documents into one of these categories.
# If a document cannot be classified, it defaults to the "other" category.
# The values are paths relative to PROCESSED_DIR.
CATEGORIES = {
    "invoices": "invoices",
    "receipts": "receipts",
    "reports": "reports",
    "letters": "letters",
    "legal": "legal",
    "medical": "medical",
    "recipes": "recipes",
    "pictures": "pictures",
    "instruction_manuals": "instruction_manuals",
    "other": "other" # Default category for unclassifiable documents
}

# --- Logging Configuration ---
# LOG_FILE: Path to the log file. If None, logs will only go to console.
LOG_FILE = os.path.join(os.path.dirname(__file__), "document_processor.log")

# LOG_LEVEL: Minimum logging level to capture. Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = "INFO"

# --- Archiving Configuration ---
# ARCHIVE_DIR: Directory where original batch PDFs will be moved after processing.
# Ensure this path is absolute and accessible by the script.
ARCHIVE_DIR = "/mnt/scans_processed/archive"

# ARCHIVE_RETENTION_DAYS: Number of days to retain files in the ARCHIVE_DIR.
# Files older than this will be automatically deleted by the cleanup function.
ARCHIVE_RETENTION_DAYS = 30

# --- Retry Mechanism Configuration ---
# MAX_RETRIES: Maximum number of times to retry a failed API request.
MAX_RETRIES = 3

# RETRY_DELAY_SECONDS: Initial delay in seconds before the first retry.
# Subsequent retries will use exponential backoff (delay * 2).
RETRY_DELAY_SECONDS = 2
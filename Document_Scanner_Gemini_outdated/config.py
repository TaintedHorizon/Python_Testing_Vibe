# config.py
# This file centralizes all the configuration settings for the document processing script.
# By modifying the variables in this file, you can change the behavior of the script
# without altering the main application logic.

import os

# --- Gemini API Configuration ---
# API_URL: The specific endpoint for the Gemini model you want to use.
# The model 'gemini-1.5-flash' is chosen for its balance of speed and capability.
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

# --- Application Settings ---
# General operational settings for the script.

# DRY_RUN: If set to True, the script will log the actions it would have taken
# (like moving files or calling the API) without actually performing them. This is useful for testing.
# Set to False for normal operation.
DRY_RUN = False

# --- Directory Configuration ---
# Defines the file paths for intake, processing, and archiving.
# **ACTION**: Update these paths to match the locations on your system.

# INTAKE_DIR: The folder where the script looks for new PDF files to process.
INTAKE_DIR = "/mnt/scans_intake"

# PROCESSED_DIR: The root folder where categorized documents will be saved.
# Subdirectories for each category will be created here automatically.
PROCESSED_DIR = "/mnt/scans_processed"

# ARCHIVE_DIR: The folder where original, successfully processed files are moved.
ARCHIVE_DIR = os.path.join(PROCESSED_DIR, "archive")

# --- Category Configuration ---
# Defines the document categories and their corresponding subfolder names.
# The keys are the category names the AI will be instructed to use.
# The values are the directory paths (relative to PROCESSED_DIR) where the files will be saved.
# You can add, remove, or change categories to fit your needs.
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
    "travel": "travel",
    "Confirmation Program": "religious/confirmation",
    "Marriage Encounter": "religious/marriage_encounter",
    "other": "other"  # A fallback category for documents that don't fit elsewhere.
}

# --- Logging Configuration ---
# Settings for how the script records its activities.

# LOG_FILE: The full path to the log file. The script will create this file if it doesn't exist.
LOG_FILE = os.path.join(os.path.dirname(__file__), "document_processor_gemini.log")

# LOG_LEVEL: The verbosity of the logs. Options are DEBUG, INFO, WARNING, ERROR, CRITICAL.
# "DEBUG" is the most verbose and is useful for development and troubleshooting.
# "INFO" is recommended for normal operation.
LOG_LEVEL = "DEBUG"

# --- Archiving Configuration ---
# Settings for managing the archive of original files.

# ARCHIVE_RETENTION_DAYS: The number of days to keep files in the archive before deleting them.
# This helps to automatically manage disk space.
ARCHIVE_RETENTION_DAYS = 30

# --- Retry Mechanism Configuration ---
# Settings for handling transient errors when communicating with the Gemini API.

# MAX_RETRIES: The maximum number of times the script will retry a failed API call.
MAX_RETRIES = 3

# RETRY_DELAY_SECONDS: The number of seconds to wait between retry attempts.
RETRY_DELAY_SECONDS = 5

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Core Application Configuration ---
# Provides default values if the environment variables are not set.
DATABASE_PATH = os.getenv("DATABASE_PATH", "documents.db")
INTAKE_DIR = os.getenv("INTAKE_DIR", "intake")
PROCESSED_DIR = os.getenv("PROCESSED_DIR", "processed")
ARCHIVE_DIR = os.getenv("ARCHIVE_DIR", "archive")
FILING_CABINET_DIR = os.getenv("FILING_CABINET_DIR", "filing_cabinet")

# --- AI Service Configuration ---
# These are expected to be set in the .env file without defaults.
OLLAMA_HOST = os.getenv("OLLAMA_HOST")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

# --- Debugging and Feature Flags ---
# Converts the string from .env to a boolean.
DEBUG_SKIP_OCR = os.getenv("DEBUG_SKIP_OCR", "False").lower() in ("true", "1", "t")

# --- Status Constants ---
# These are application-level constants and are not meant to be configured.
STATUS_PENDING_VERIFICATION = "pending_verification"
STATUS_FAILED = "failed"

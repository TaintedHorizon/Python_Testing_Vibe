# config.py
import os

# --- General Settings ---
# Set to True to prevent the script from making any actual file changes (moving, deleting).
# It will only log the actions it would have taken.
DRY_RUN = False

# --- Ollama LLM Configuration ---
# The hostname or IP address of your Ollama server.
OLLAMA_HOST = "http://192.168.2.225:11434"
# The specific model to use for analysis (e.g., "llama3.1:8b", "llava:latest").
OLLAMA_MODEL = "llama3.1:8b"
# The maximum context window size the model should use. For llama3, 8192 is a safe default.
OLLAMA_CONTEXT_WINDOW = 8192

# --- Directory Paths ---
# The absolute path to the folder where new scans are placed.
INTAKE_DIR = "/mnt/scans_intake"
# The absolute path to the root folder where processed documents will be saved.
PROCESSED_DIR = "/mnt/scans_processed"
# The absolute path to the folder where original files will be moved after successful processing.
ARCHIVE_DIR = os.path.join(PROCESSED_DIR, "archive")

# --- Document Categories ---
# A dictionary defining the BROAD document categories and their target subdirectories within PROCESSED_DIR.
# The AI will first group documents into these high-level categories.
CATEGORIES = {
    "Travel Documents": "travel",
    "Vehicle Documents": "vehicle",
    "Financial Documents": "financial",
    "Religious Documents": "religious",
    "Personal Documents": "personal",
    "other": "other",
}

# --- Logging Configuration ---
# The absolute path to the log file.
LOG_FILE = os.path.join(os.path.dirname(__file__), "document_processor_ollama.log")
# Minimum logging level. Options: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL".
LOG_LEVEL = "INFO"

# --- Archiving and Retries ---
# The number of days to keep original files in the archive before deleting them.
ARCHIVE_RETENTION_DAYS = 30
# The number of times to retry a failed AI call.
MAX_RETRIES = 3
# The number of seconds to wait between retries.
RETRY_DELAY_SECONDS = 5
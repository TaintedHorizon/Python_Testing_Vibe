"""
Configuration management for the document processing system.
Provides a centralized, type-safe configuration with validation.

🤖 AI ASSISTANTS: This is the ONLY config module to use!
See .github/copilot-instructions.md - NEVER import from old 'config.py'
"""
import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
import logging

@dataclass
class AppConfig:
    # --- Archive Retention ---
    ARCHIVE_RETENTION_DAYS: int = 30
    """Application configuration with validation and type safety."""
    # --- Core Application Configuration ---
    DATABASE_PATH: str = "documents.db"
    INTAKE_DIR: str = "intake"
    PROCESSED_DIR: str = "processed"
    ARCHIVE_DIR: str = "archive"
    FILING_CABINET_DIR: str = "filing_cabinet"

    # --- AI Service Configuration ---
    OLLAMA_HOST: Optional[str] = None
    OLLAMA_MODEL: Optional[str] = None
    OLLAMA_CONTEXT_WINDOW: Optional[int] = 8192
    OLLAMA_NUM_GPU: Optional[int] = None
    OLLAMA_TIMEOUT: int = 45
    
    # --- Task-Specific Context Windows ---
    OLLAMA_CTX_CLASSIFICATION: int = 2048
    OLLAMA_CTX_DETECTION: int = 2048
    OLLAMA_CTX_CATEGORY: int = 2048
    OLLAMA_CTX_ORDERING: int = 2048
    OLLAMA_CTX_TITLE_GENERATION: int = 4096

    # --- Logging Configuration ---
    LOG_FILE_PATH: str = "logs/app.log"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5  # Keep 5 backup files
    LOG_LEVEL: str = "INFO"

    # --- Debugging and Feature Flags ---
    DEBUG_SKIP_OCR: bool = False
    ENABLE_TAG_EXTRACTION: bool = True  # Enable LLM-powered tag extraction during export

    # --- Status Constants ---
    # These are application-level constants and are not meant to be configured
    STATUS_PENDING_VERIFICATION: str = "pending_verification"
    STATUS_VERIFICATION_COMPLETE: str = "verification_complete"
    STATUS_GROUPING_COMPLETE: str = "grouping_complete"
    STATUS_ORDERING_COMPLETE: str = "ordering_complete"
    STATUS_EXPORTED: str = "exported"
    STATUS_FAILED: str = "failed"
    STATUS_READY_FOR_MANIPULATION: str = "ready_for_manipulation"

    @classmethod
    def load_from_env(cls) -> 'AppConfig':
        """
        Creates a configuration instance from environment variables.
        Validates required paths and settings.
        
        Returns:
            AppConfig: Validated configuration instance
        
        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Try to load .env from workspace root, then from doc_processor/
        from dotenv import load_dotenv
        import pathlib
        env_loaded = load_dotenv()
        if not env_loaded:
            # Try loading from doc_processor/.env explicitly
            env_path = pathlib.Path(__file__).parent / ".env"
            load_dotenv(dotenv_path=env_path)

        # Helper function to get environment variable with default
        def get_env(key: str, default: str) -> str:
            """Get environment variable with a required default value."""
            value = os.getenv(key)
            if value is not None:
                value = value.strip('"').strip("'")
            return value if value is not None else default

        # Helper function to get optional environment variable
        def get_optional_env(key: str) -> Optional[str]:
            """Get environment variable that can be None."""
            value = os.getenv(key)
            if value is not None:
                value = value.strip('"').strip("'")
            return value

        # Helper function to validate directory path
        def validate_directory(path: str, key: str) -> str:
            try:
                path = os.path.abspath(path)
                os.makedirs(path, exist_ok=True)
                if not os.access(path, os.R_OK | os.W_OK):
                    raise ValueError(f"Insufficient permissions for {key} directory: {path}")
                return path
            except OSError as e:
                raise ValueError(f"Invalid {key} directory {path}: {e}")

        # Construct and validate configuration
        try:
            archive_retention_days = int(os.getenv("ARCHIVE_RETENTION_DAYS", "30"))
            ollama_num_gpu = os.getenv("OLLAMA_NUM_GPU")
            ollama_num_gpu = int(ollama_num_gpu) if ollama_num_gpu is not None and ollama_num_gpu != "" else None
            ollama_timeout = int(os.getenv("OLLAMA_TIMEOUT", "45"))
            config = cls(
                # Core Application Configuration
                DATABASE_PATH=get_env("DATABASE_PATH", cls.DATABASE_PATH),
                INTAKE_DIR=validate_directory(get_env("INTAKE_DIR", cls.INTAKE_DIR), "INTAKE"),
                PROCESSED_DIR=validate_directory(get_env("PROCESSED_DIR", cls.PROCESSED_DIR), "PROCESSED"),
                ARCHIVE_DIR=validate_directory(get_env("ARCHIVE_DIR", cls.ARCHIVE_DIR), "ARCHIVE"),
                FILING_CABINET_DIR=validate_directory(get_env("FILING_CABINET_DIR", cls.FILING_CABINET_DIR), "FILING_CABINET"),
                ARCHIVE_RETENTION_DAYS=archive_retention_days,
                
                # AI Service Configuration
                OLLAMA_HOST=get_optional_env("OLLAMA_HOST"),
                OLLAMA_MODEL=get_optional_env("OLLAMA_MODEL"),
                OLLAMA_CONTEXT_WINDOW=int(get_env("OLLAMA_CONTEXT_WINDOW", str(cls.OLLAMA_CONTEXT_WINDOW))),
                OLLAMA_NUM_GPU=ollama_num_gpu,
                OLLAMA_TIMEOUT=ollama_timeout,
                
                # Task-Specific Context Windows
                OLLAMA_CTX_CLASSIFICATION=int(get_env("OLLAMA_CTX_CLASSIFICATION", str(cls.OLLAMA_CTX_CLASSIFICATION))),
                OLLAMA_CTX_DETECTION=int(get_env("OLLAMA_CTX_DETECTION", str(cls.OLLAMA_CTX_DETECTION))),
                OLLAMA_CTX_CATEGORY=int(get_env("OLLAMA_CTX_CATEGORY", str(cls.OLLAMA_CTX_CATEGORY))),
                OLLAMA_CTX_ORDERING=int(get_env("OLLAMA_CTX_ORDERING", str(cls.OLLAMA_CTX_ORDERING))),
                OLLAMA_CTX_TITLE_GENERATION=int(get_env("OLLAMA_CTX_TITLE_GENERATION", str(cls.OLLAMA_CTX_TITLE_GENERATION))),
                
                # Logging Configuration
                LOG_FILE_PATH=get_env("LOG_FILE_PATH", cls.LOG_FILE_PATH),
                LOG_MAX_BYTES=int(get_env("LOG_MAX_BYTES", str(cls.LOG_MAX_BYTES))),
                LOG_BACKUP_COUNT=int(get_env("LOG_BACKUP_COUNT", str(cls.LOG_BACKUP_COUNT))),
                LOG_LEVEL=get_env("LOG_LEVEL", cls.LOG_LEVEL),

                # Debugging and Feature Flags
                DEBUG_SKIP_OCR=get_env("DEBUG_SKIP_OCR", str(cls.DEBUG_SKIP_OCR)).lower() in ("true", "1", "t"),
                ENABLE_TAG_EXTRACTION=get_env("ENABLE_TAG_EXTRACTION", str(cls.ENABLE_TAG_EXTRACTION)).lower() in ("true", "1", "t"),
                
                # Status Constants (these are not loaded from environment)
                STATUS_PENDING_VERIFICATION=cls.STATUS_PENDING_VERIFICATION,
                STATUS_VERIFICATION_COMPLETE=cls.STATUS_VERIFICATION_COMPLETE,
                STATUS_GROUPING_COMPLETE=cls.STATUS_GROUPING_COMPLETE,
                STATUS_ORDERING_COMPLETE=cls.STATUS_ORDERING_COMPLETE,
                STATUS_EXPORTED=cls.STATUS_EXPORTED,
                STATUS_FAILED=cls.STATUS_FAILED,
                STATUS_READY_FOR_MANIPULATION=cls.STATUS_READY_FOR_MANIPULATION
            )
            
            # Validate database path
            db_dir = os.path.dirname(config.DATABASE_PATH)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            
            return config

        except Exception as e:
            logging.error(f"Configuration error: {e}")
            raise

# Status constants
STATUS_PENDING_VERIFICATION = "pending_verification"
STATUS_FAILED = "failed"
STATUS_VERIFICATION_COMPLETE = "verification_complete"
STATUS_GROUPING_COMPLETE = "grouping_complete"
STATUS_ORDERING_COMPLETE = "ordering_complete"
STATUS_EXPORTED = "exported"
STATUS_READY_FOR_MANIPULATION = "ready_for_manipulation"

# Default categories that should always be available
DEFAULT_CATEGORIES = [
    "Invoice",
    "Receipt",
    "Statement",
    "Contract",
    "Report",
    "Correspondence",
    "Other"
]

# Create a global config instance
try:
    app_config = AppConfig.load_from_env()
except Exception as e:
    logging.critical(f"Failed to load configuration: {e}")
    raise
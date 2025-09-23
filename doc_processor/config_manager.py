"""
Configuration management for the document processing system.
Provides a centralized, type-safe configuration with validation.
"""
import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
import logging

@dataclass
class AppConfig:
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

    # --- Debugging and Feature Flags ---
    DEBUG_SKIP_OCR: bool = False

    # --- Status Constants ---
    # These are application-level constants and are not meant to be configured
    STATUS_PENDING_VERIFICATION: str = "pending_verification"
    STATUS_VERIFICATION_COMPLETE: str = "verification_complete"
    STATUS_GROUPING_COMPLETE: str = "grouping_complete"
    STATUS_ORDERING_COMPLETE: str = "ordering_complete"
    STATUS_EXPORTED: str = "exported"
    STATUS_FAILED: str = "failed"

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
        load_dotenv()  # Load .env file if it exists

        # Helper function to get environment variable with default
        def get_env(key: str, default: str) -> str:
            """Get environment variable with a required default value."""
            value = os.getenv(key)
            return value if value is not None else default

        # Helper function to get optional environment variable
        def get_optional_env(key: str) -> Optional[str]:
            """Get environment variable that can be None."""
            return os.getenv(key)

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
            config = cls(
                # Core Application Configuration
                DATABASE_PATH=get_env("DATABASE_PATH", cls.DATABASE_PATH),
                INTAKE_DIR=validate_directory(get_env("INTAKE_DIR", cls.INTAKE_DIR), "INTAKE"),
                PROCESSED_DIR=validate_directory(get_env("PROCESSED_DIR", cls.PROCESSED_DIR), "PROCESSED"),
                ARCHIVE_DIR=validate_directory(get_env("ARCHIVE_DIR", cls.ARCHIVE_DIR), "ARCHIVE"),
                FILING_CABINET_DIR=validate_directory(get_env("FILING_CABINET_DIR", cls.FILING_CABINET_DIR), "FILING_CABINET"),
                
                # AI Service Configuration
                OLLAMA_HOST=get_optional_env("OLLAMA_HOST"),
                OLLAMA_MODEL=get_optional_env("OLLAMA_MODEL"),
                OLLAMA_CONTEXT_WINDOW=int(get_env("OLLAMA_CONTEXT_WINDOW", str(cls.OLLAMA_CONTEXT_WINDOW))),
                
                # Debugging and Feature Flags
                DEBUG_SKIP_OCR=get_env("DEBUG_SKIP_OCR", str(cls.DEBUG_SKIP_OCR)).lower() in ("true", "1", "t"),
                
                # Status Constants (these are not loaded from environment)
                STATUS_PENDING_VERIFICATION=cls.STATUS_PENDING_VERIFICATION,
                STATUS_VERIFICATION_COMPLETE=cls.STATUS_VERIFICATION_COMPLETE,
                STATUS_GROUPING_COMPLETE=cls.STATUS_GROUPING_COMPLETE,
                STATUS_ORDERING_COMPLETE=cls.STATUS_ORDERING_COMPLETE,
                STATUS_EXPORTED=cls.STATUS_EXPORTED,
                STATUS_FAILED=cls.STATUS_FAILED
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
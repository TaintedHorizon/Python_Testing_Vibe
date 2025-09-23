"""
Custom exceptions for the document processing system.
Provides specific exception types for different error scenarios.
"""
from typing import Optional

class DocProcessorError(Exception):
    """Base exception class for document processor errors."""
    def __init__(self, message: str, details: Optional[str] = None):
        self.message = message
        self.details = details
        super().__init__(self.message)

class ConfigurationError(DocProcessorError):
    """Raised when there is an error in configuration."""
    pass

class FileProcessingError(DocProcessorError):
    """Raised when there is an error processing a file."""
    pass

class OCRError(DocProcessorError):
    """Raised when there is an error during OCR processing."""
    pass

class DatabaseError(DocProcessorError):
    """Raised when there is a database-related error."""
    pass

class AIServiceError(DocProcessorError):
    """Raised when there is an error communicating with the AI service."""
    pass

class ValidationError(DocProcessorError):
    """Raised when input validation fails."""
    pass

class ExportError(DocProcessorError):
    """Raised when there is an error during document export."""
    pass
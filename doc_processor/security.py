"""
Security middleware and utilities for the document processing system.
"""
from functools import wraps
from flask import request, abort
import re
from typing import Callable, List, Optional
import logging

def validate_path(path: str) -> bool:
    """
    Validates that a path is safe and contains no directory traversal attempts.
    
    Args:
        path: Path to validate
        
    Returns:
        bool: True if path is safe, False otherwise
    """
    # Remove any Windows-style backslashes
    normalized_path = path.replace('\\', '/')
    
    # Check for common directory traversal patterns
    traversal_patterns = [
        r'\.\.',         # Parent directory references
        r'//+',          # Multiple forward slashes
        r'^/|^\\',       # Absolute paths
        r'~'             # Home directory references
    ]
    
    return not any(re.search(pattern, normalized_path) for pattern in traversal_patterns)

def sanitize_input(value: str) -> str:
    """
    Sanitizes user input to prevent injection attacks.
    
    Args:
        value: String to sanitize
        
    Returns:
        str: Sanitized string
    """
    # Remove any non-printable characters
    sanitized = ''.join(char for char in value if char.isprintable())
    
    # Remove any HTML tags
    sanitized = re.sub(r'<[^>]*>', '', sanitized)
    
    return sanitized

def require_safe_path(f: Callable) -> Callable:
    """
    Decorator to ensure all path parameters are safe.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check path parameters
        path_params = [v for v in kwargs.values() if isinstance(v, str) and ('path' in v.lower() or 'dir' in v.lower())]
        for path in path_params:
            if not validate_path(path):
                logging.warning(f"Invalid path attempt: {path}")
                abort(400, "Invalid path")
        return f(*args, **kwargs)
    return decorated_function

def validate_file_upload(file_content: bytes, allowed_extensions: Optional[List[str]] = None) -> bool:
    """
    Validates file uploads for safety.
    
    Args:
        file_content: Content of the uploaded file
        allowed_extensions: List of allowed file extensions
        
    Returns:
        bool: True if file is safe, False otherwise
    """
    # Check file size
    if len(file_content) > 10 * 1024 * 1024:  # 10MB limit
        return False
        
    # Check file magic numbers for common formats
    magic_numbers = {
        b'%PDF': '.pdf',
        b'\xFF\xD8\xFF': '.jpg',
        b'\x89PNG': '.png'
    }
    
    file_type = None
    for magic, ext in magic_numbers.items():
        if file_content.startswith(magic):
            file_type = ext
            break
            
    if not file_type:
        return False
        
    if allowed_extensions and file_type.lower() not in allowed_extensions:
        return False
        
    return True

def sanitize_filename(filename: str) -> str:
    """
    Sanitizes a filename to be safe for filesystem operations.
    
    Args:
        filename: Original filename
        
    Returns:
        str: Sanitized filename
    """
    # Remove any directory components
    filename = filename.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
    
    # Remove any non-alphanumeric characters except for dots, convert to underscores for consistency
    filename = re.sub(r'[^a-zA-Z0-9.]', '_', filename)
    
    # Ensure the filename isn't too long
    MAX_LENGTH = 255
    name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
    if len(name) + len(ext) + 1 > MAX_LENGTH:
        name = name[:(MAX_LENGTH - len(ext) - 1)]
    
    return f"{name}.{ext}" if ext else name
"""
Utility functions for Flask application

This module contains helper functions that were scattered throughout the monolithic app.py.
Benefits of extracting utilities:
- Reusable functions across multiple route files
- Easier to test in isolation
- Cleaner route files focused on HTTP handling
- Better organization of common functionality
"""

import os
import logging
from typing import List, Dict, Any, Optional

def get_supported_files(directory: str) -> List[str]:
    """
    Get all supported files (PDFs and images) from a directory.

    Args:
        directory: Path to directory to scan

    Returns:
        List of absolute paths to supported files
    """
    if not os.path.exists(directory):
        return []

    supported_extensions = ['.pdf', '.png', '.jpg', '.jpeg']
    supported_files = []

    for filename in os.listdir(directory):
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext in supported_extensions:
            supported_files.append(os.path.join(directory, filename))

    return sorted(supported_files)

def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string like "1.5 MB"
    """
    if size_bytes == 0:
        return "0 B"

    size: float = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0

    return f"{size:.1f} TB"

def validate_file_type(filename: str, allowed_types: Optional[List[str]] = None) -> bool:
    """
    Validate if a file has an allowed extension.

    Args:
        filename: Name of file to check
        allowed_types: List of allowed extensions (with dots)

    Returns:
        True if file type is allowed
    """
    if allowed_types is None:
        allowed_types = ['.pdf', '.png', '.jpg', '.jpeg']

    file_ext = os.path.splitext(filename)[1].lower()
    return file_ext in allowed_types

def safe_filename(filename: str) -> str:
    """
    Create a safe filename by removing/replacing problematic characters.

    Args:
        filename: Original filename

    Returns:
        Safe filename suitable for filesystem
    """
    import re
    # Remove path components and problematic characters
    safe_name = os.path.basename(filename)
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', safe_name)
    safe_name = re.sub(r'\s+', '_', safe_name)
    return safe_name

def log_route_access(route_name: str, user_id: Optional[str] = None, extra_data: Optional[Dict[str, Any]] = None):
    """
    Log route access for debugging and analytics.

    Args:
        route_name: Name of the route being accessed
        user_id: Optional user identifier
        extra_data: Optional additional data to log
    """
    log_data = {
        'route': route_name,
        'user_id': user_id or 'anonymous',
        'timestamp': 'auto'
    }

    if extra_data:
        log_data.update(extra_data)

    logging.info(f"Route access: {log_data}")

def create_error_response(error_message: str, status_code: int = 500) -> Dict[str, Any]:
    """
    Create standardized error response format.

    Args:
        error_message: Error message to return
        status_code: HTTP status code

    Returns:
        Dictionary with error response data
    """
    return {
        'error': error_message,
        'success': False,
        'status_code': status_code
    }

def create_success_response(data: Any = None, message: Optional[str] = None) -> Dict[str, Any]:
    """
    Create standardized success response format.

    Args:
        data: Optional data to include in response
        message: Optional success message

    Returns:
        Dictionary with success response data
    """
    response = {
        'success': True,
        'status_code': 200
    }

    if data is not None:
        response['data'] = data

    if message:
        response['message'] = message

    return response
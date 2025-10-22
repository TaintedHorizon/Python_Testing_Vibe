#!/usr/bin/env python3
"""
Tests for image support and image-to-PDF conversion.

Moved from doc_processor/dev_tools/test_image_support.py and adapted to package imports.
"""
import os
from typing import Any, cast
from PIL import Image
from doc_processor.processing import is_image_file

def test_image_to_pdf_conversion(tmp_path):
    """Test the basic image-to-PDF conversion functionality."""
    from doc_processor.processing import convert_image_to_pdf

    # Create a simple test image
    temp_img_path = str(tmp_path / 'temp_img.png')
    img = Image.new('RGB', (100, 100), color=cast(Any, (255, 0, 0)))
    img.save(temp_img_path, 'PNG')

    # Test is_image_file function
    assert is_image_file(temp_img_path), "PNG file should be detected as image"
    assert not is_image_file('test.pdf'), "PDF file should not be detected as image"

    # Test image-to-PDF conversion
    temp_pdf_path = str(tmp_path / 'converted1.pdf')
    convert_image_to_pdf(temp_img_path, temp_pdf_path)

    # Verify the PDF was created
    assert os.path.exists(temp_pdf_path), "PDF file should be created"
    assert os.path.getsize(temp_pdf_path) > 0, "PDF file should not be empty"

    # Test with JPEG
    temp_jpg_path = str(tmp_path / 'temp_jpg.jpg')
    img = Image.new('RGB', (100, 100), color=cast(Any, (0, 0, 255)))
    img.save(temp_jpg_path, 'JPEG')
    temp_pdf2_path = str(tmp_path / 'converted2.pdf')
    convert_image_to_pdf(temp_jpg_path, temp_pdf2_path)
    assert os.path.exists(temp_pdf2_path), "JPEG-to-PDF conversion should work"

    # Cleanup
    # cleanup handled by tmp_path fixture


def test_document_detector_with_images(tmp_path):
    """Test the document detector with image files."""
    from doc_processor.document_detector import get_detector

    # Create a test image
    temp_img_path = str(tmp_path / 'detector_img.png')
    img = Image.new('RGB', (200, 300), color=cast(Any, (255, 255, 255)))
    img.save(temp_img_path, 'PNG')

    # Test the detector
    detector = get_detector(use_llm_for_ambiguous=False)  # Disable LLM for testing
    analysis = detector.analyze_image_file(temp_img_path)

    # Basic assertions
    assert analysis.processing_strategy in ['single_document', 'batch_scan'], "Should return valid strategy"
    assert analysis.page_count == 1, "Images should have page count of 1"
    assert analysis.file_size_mb >= 0, "File size should be non-negative"

    # Cleanup
    # tmp_path fixture will clean up


def test_supported_file_detection():
    """Test that the system detects supported file types correctly."""
    # Create test directory with various file types using tmp_path
    from pathlib import Path
    temp_dir = Path(os.environ.get('TEST_SUPPORTED_DIR') or os.getenv('TMPDIR') or '/tmp')
    # If pytest provided tmp_path via env (preferred), use it; otherwise use system tempdir
    # For focused runs, callers can set TEST_SUPPORTED_DIR to a tmp_path location.

    # Create a dedicated subdir to avoid collisions
    temp_dir = Path(temp_dir) / f"test_supported_{os.getpid()}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Create test files
    test_files = [
        ('test.pdf', b'dummy pdf content'),
        ('image.png', b'dummy png content'),
        ('photo.jpg', b'dummy jpg content'),
        ('picture.jpeg', b'dummy jpeg content'),
        ('document.txt', b'dummy text content'),  # Should be ignored
        ('data.csv', b'dummy csv content'),        # Should be ignored
    ]

    for filename, content in test_files:
        with open(os.path.join(str(temp_dir), filename), 'wb') as f:
            f.write(content)

    # Test file detection
    from doc_processor.document_detector import get_detector
    detector = get_detector(use_llm_for_ambiguous=False)

    # Get all supported files
    supported_extensions = ['.pdf', '.png', '.jpg', '.jpeg']
    supported_files = [f for f in os.listdir(str(temp_dir)) if os.path.splitext(f)[1].lower() in supported_extensions]

    # Should find 4 supported files (PDF, PNG, JPG, JPEG)
    assert len(supported_files) == 4, f"Should find 4 supported files, found {len(supported_files)}"

    expected_files = {'test.pdf', 'image.png', 'photo.jpg', 'picture.jpeg'}
    actual_files = set(supported_files)
    assert actual_files == expected_files, f"Expected {expected_files}, got {actual_files}"

    # Clean up the created directory
    try:
        import shutil
        shutil.rmtree(str(temp_dir))
    except Exception:
        pass

# Note: earlier duplicate test functions were removed to avoid redefinition errors

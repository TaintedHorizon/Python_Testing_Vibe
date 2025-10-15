#!/usr/bin/env python3
"""
Tests for image support and image-to-PDF conversion.

Moved from doc_processor/dev_tools/test_image_support.py and adapted to package imports.
"""
import os
import tempfile
from PIL import Image
from doc_processor.processing import is_image_file

def test_image_to_pdf_conversion():
    """Test the basic image-to-PDF conversion functionality."""
    from doc_processor.processing import convert_image_to_pdf

    # Create a simple test image
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_img:
        img = Image.new('RGB', (100, 100), color=(255, 0, 0))
        img.save(temp_img.name, 'PNG')
        temp_img_path = temp_img.name

    # Test is_image_file function
    assert is_image_file(temp_img_path), "PNG file should be detected as image"
    assert not is_image_file('test.pdf'), "PDF file should not be detected as image"

    # Test image-to-PDF conversion
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
        temp_pdf_path = temp_pdf.name

    convert_image_to_pdf(temp_img_path, temp_pdf_path)

    # Verify the PDF was created
    assert os.path.exists(temp_pdf_path), "PDF file should be created"
    assert os.path.getsize(temp_pdf_path) > 0, "PDF file should not be empty"

    # Test with JPEG
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_jpg:
        img = Image.new('RGB', (100, 100), color=(0, 0, 255))
        img.save(temp_jpg.name, 'JPEG')
        temp_jpg_path = temp_jpg.name

    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf2:
        temp_pdf2_path = temp_pdf2.name

    convert_image_to_pdf(temp_jpg_path, temp_pdf2_path)
    assert os.path.exists(temp_pdf2_path), "JPEG-to-PDF conversion should work"

    # Cleanup
    for path in [temp_img_path, temp_pdf_path, temp_jpg_path, temp_pdf2_path]:
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass


def test_document_detector_with_images():
    """Test the document detector with image files."""
    from doc_processor.document_detector import get_detector

    # Create a test image
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_img:
        img = Image.new('RGB', (200, 300), color=(255, 255, 255))
        img.save(temp_img.name, 'PNG')
        temp_img_path = temp_img.name

    # Test the detector
    detector = get_detector(use_llm_for_ambiguous=False)  # Disable LLM for testing
    analysis = detector.analyze_image_file(temp_img_path)

    # Basic assertions
    assert analysis.processing_strategy in ['single_document', 'batch_scan'], "Should return valid strategy"
    assert analysis.page_count == 1, "Images should have page count of 1"
    assert analysis.file_size_mb >= 0, "File size should be non-negative"

    # Cleanup
    try:
        if os.path.exists(temp_img_path):
            os.unlink(temp_img_path)
    except Exception:
        pass


def test_supported_file_detection():
    """Test that the system detects supported file types correctly."""
    import tempfile

    # Create test directory with various file types
    with tempfile.TemporaryDirectory() as temp_dir:
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
            with open(os.path.join(temp_dir, filename), 'wb') as f:
                f.write(content)

        # Test file detection
        from doc_processor.document_detector import get_detector
        detector = get_detector(use_llm_for_ambiguous=False)

        # Get all supported files
        supported_extensions = ['.pdf', '.png', '.jpg', '.jpeg']
        supported_files = [f for f in os.listdir(temp_dir) if os.path.splitext(f)[1].lower() in supported_extensions]

        # Should find 4 supported files (PDF, PNG, JPG, JPEG)
        assert len(supported_files) == 4, f"Should find 4 supported files, found {len(supported_files)}"

        expected_files = {'test.pdf', 'image.png', 'photo.jpg', 'picture.jpeg'}
        actual_files = set(supported_files)
        assert actual_files == expected_files, f"Expected {expected_files}, got {actual_files}"

# Note: earlier duplicate test functions were removed to avoid redefinition errors

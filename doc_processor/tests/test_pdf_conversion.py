#!/usr/bin/env python3
"""
Test script to verify image-to-PDF conversion functionality
"""

import os
import tempfile
from PIL import Image
from document_detector import DocumentTypeDetector

def test_image_to_pdf_conversion():
    """Test the image to PDF conversion functionality"""
    print("🧪 Testing image-to-PDF conversion...")

    # Create a test image
    test_image_path = os.path.join(tempfile.gettempdir(), "test_conversion.png")
    print(f"📝 Creating test image: {test_image_path}")

    try:
        # Create a simple test image
        img = Image.new('RGB', (800, 600), color='lightblue')
        img.save(test_image_path, 'PNG')
        print(f"✅ Test image created: {os.path.getsize(test_image_path)} bytes")

        # Test the conversion
        detector = DocumentTypeDetector()
        pdf_path = detector._convert_image_to_pdf(test_image_path)

        # Verify the conversion
        if os.path.exists(pdf_path):
            pdf_size = os.path.getsize(pdf_path)
            print("✅ PDF conversion successful!")
            print(f"   Original image: {test_image_path}")
            print(f"   Converted PDF: {pdf_path}")
            print(f"   PDF size: {pdf_size} bytes")

            # Test with analyze_image_file
            analysis = detector.analyze_image_file(test_image_path)
            print("✅ Full analysis test:")
            print(f"   Strategy: {analysis.processing_strategy}")
            print(f"   Confidence: {analysis.confidence}")
            print(f"   PDF path: {analysis.pdf_path}")
            print(f"   PDF exists: {os.path.exists(analysis.pdf_path) if analysis.pdf_path else False}")

        else:
            print("❌ PDF conversion failed - file not created")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up test files
        for file_path in [test_image_path]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"🧹 Cleaned up: {file_path}")
                except:
                    pass

if __name__ == "__main__":
    test_image_to_pdf_conversion()
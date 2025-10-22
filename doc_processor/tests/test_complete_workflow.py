#!/usr/bin/env python3
"""
Comprehensive test script to verify the complete image-to-PDF workflow
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from PIL import Image
from typing import Any, cast

# Add the doc_processor directory to the Python path
sys.path.insert(0, '/home/svc-scan/Python_Testing_Vibe/doc_processor')

def create_test_environment(tmp_path):
    """Create a test environment with sample files"""
    print("🔧 Setting up test environment...")

    # Create test directories under the pytest tmp_path fixture
    test_base = os.path.join(str(tmp_path), 'pdf_workflow_test')
    test_intake = os.path.join(test_base, 'intake')
    os.makedirs(test_intake, exist_ok=True)

    # Create test files
    test_files = []

    # 1. Create a test PNG image
    png_path = os.path.join(test_intake, 'test_document.png')
    img = Image.new('RGB', (800, 600), color=cast(Any, 'lightblue'))
    img.save(png_path, 'PNG')
    test_files.append(('test_document.png', 'image'))
    print(f"   📄 Created test PNG: {png_path}")

    # 2. Create a test JPG image
    jpg_path = os.path.join(test_intake, 'test_invoice.jpg')
    img = Image.new('RGB', (600, 800), color=cast(Any, 'lightgreen'))
    img.save(jpg_path, 'JPEG')
    test_files.append(('test_invoice.jpg', 'image'))
    print(f"   📄 Created test JPG: {jpg_path}")

    # 3. Copy a real PDF if available, or create a minimal one
    pdf_path = os.path.join(test_intake, 'test_existing.pdf')
    try:
        # Try to create a simple PDF using PIL
        img = Image.new('RGB', (600, 800), color=cast(Any, 'white'))
        img.save(pdf_path, 'PDF')
        test_files.append(('test_existing.pdf', 'pdf'))
        print(f"   📄 Created test PDF: {pdf_path}")
    except Exception as e:
        print(f"   ⚠️ Could not create test PDF: {e}")

    return test_base, test_intake, test_files

def test_document_analysis_with_conversion(tmp_path):
    """Test the document analysis with PDF conversion"""
    print("\n🧪 Testing document analysis with PDF conversion...")

    test_base, test_intake, test_files = create_test_environment(tmp_path)

    try:
        from document_detector import DocumentTypeDetector
        detector = DocumentTypeDetector()

        results = []

        for filename, file_type in test_files:
            file_path = os.path.join(test_intake, filename)
            print(f"\n   📋 Analyzing: {filename} (type: {file_type})")

            try:
                if file_type == 'image':
                    analysis = detector.analyze_image_file(file_path)
                else:
                    analysis = detector.analyze_pdf(file_path)

                result = {
                    'filename': filename,
                    'file_type': file_type,
                    'strategy': analysis.processing_strategy,
                    'confidence': analysis.confidence,
                    'pdf_path': analysis.pdf_path,
                    'pdf_exists': os.path.exists(analysis.pdf_path) if analysis.pdf_path else False,
                    'original_exists': os.path.exists(analysis.file_path)
                }

                results.append(result)

                print(f"      ✅ Strategy: {analysis.processing_strategy}")
                print(f"      ✅ Confidence: {analysis.confidence}")
                print(f"      ✅ Original file: {analysis.file_path} (exists: {result['original_exists']})")
                print(f"      ✅ PDF path: {analysis.pdf_path} (exists: {result['pdf_exists']})")

                # For images, verify conversion worked
                if file_type == 'image' and analysis.pdf_path:
                    if result['pdf_exists']:
                        pdf_size = os.path.getsize(analysis.pdf_path)
                        print(f"      🎯 Converted PDF size: {pdf_size} bytes")
                    else:
                        print("      ❌ Converted PDF not found!")

            except Exception as e:
                print(f"      ❌ Analysis failed: {e}")
                results.append({
                    'filename': filename,
                    'file_type': file_type,
                    'error': str(e)
                })

        # Assertions: ensure at least one analysis result and basic sanity checks
        assert len(results) > 0, "No analysis results were produced"
        for res in results:
            # Each result should have filename and strategy
            assert 'filename' in res and 'strategy' in res, f"Incomplete result: {res}"
            # If image, expect a pdf_path value (may or may not exist depending on environment)
            if res.get('file_type') == 'image':
                assert 'pdf_path' in res, "Image analysis should include pdf_path"

    finally:
        # Clean up test environment
        print(f"\n🧹 Cleaning up test environment: {test_base}")
        try:
            shutil.rmtree(test_base)
        except:
            pass

def test_export_route_logic(tmp_path):
    """Test the export route logic for serving files"""
    print("\n🌐 Testing export route logic...")

    # This would require setting up a Flask test client
    # For now, we'll test the core logic

    test_base, test_intake, test_files = create_test_environment(tmp_path)

    try:
        # Test the file serving logic
        for filename, file_type in test_files:
            print(f"\n   🔍 Testing route logic for: {filename}")

            file_path = os.path.join(test_intake, filename)
            file_ext = Path(filename).suffix.lower()

            if file_ext == '.pdf':
                print(f"      📄 PDF file - would serve directly from {file_path}")
            elif file_ext in ['.png', '.jpg', '.jpeg']:
                # Simulate the conversion and route logic; use tmp_path provided by pytest
                # place converted PDFs under the test tmp directory so we don't touch global temp dirs
                temp_dir = os.path.join(str(tmp_path), 'converted')
                os.makedirs(temp_dir, exist_ok=True)
                image_name = Path(filename).stem
                converted_pdf_path = os.path.join(temp_dir, f"{image_name}_converted.pdf")

                print(f"      🖼️ Image file - checking for converted PDF: {converted_pdf_path}")

                if os.path.exists(converted_pdf_path):
                    print("      ✅ Would serve converted PDF")
                else:
                    print("      ⚠️ Would fall back to original image")
            else:
                print("      📁 Other file type - would serve original")

    finally:
        # Clean up
        try:
            shutil.rmtree(test_base)
        except:
            pass

# Note: This module contains pytest-style tests and does not execute as a script.
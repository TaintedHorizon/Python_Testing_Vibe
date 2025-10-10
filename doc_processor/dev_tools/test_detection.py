#!/usr/bin/env python3
"""
Test script to validate document type detection heuristics.

This script helps verify the accuracy of the conservative detection logic
before processing real documents.
"""

import os
import sys
from pathlib import Path

# Add doc_processor to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from document_detector import get_detector

def test_detection_with_sample_files():
    """Test detection on sample files if available."""
    detector = get_detector()
    
    # Check if there are files in intake directory
    from config_manager import app_config
    
    if not os.path.exists(app_config.INTAKE_DIR):
        pytest.skip(f"Intake directory not found: {app_config.INTAKE_DIR}")
    
    # Analyze current intake
    analyses = detector.analyze_intake_directory(app_config.INTAKE_DIR)
    
    if not analyses:
        pytest.skip(f"No PDF files found in intake directory: {app_config.INTAKE_DIR}")
    
    print("=== DOCUMENT DETECTION TEST RESULTS ===\n")
    
    single_docs = []
    batch_scans = []
    
    for analysis in analyses:
        filename = os.path.basename(analysis.file_path)
        strategy = analysis.processing_strategy
        confidence = analysis.confidence
        
        print(f"File: {filename}")
        print(f"  Size: {analysis.file_size_mb:.1f}MB, Pages: {analysis.page_count}")
        print(f"  Strategy: {strategy} (confidence: {confidence:.2f})")
        print(f"  Filename hint: {analysis.filename_hints}")
        
        if analysis.content_sample:
            print(f"  Content sample: {analysis.content_sample[:100]}...")
        
        print("  Reasoning:")
        for reason in analysis.reasoning:
            print(f"    - {reason}")
        
        if strategy == "single_document":
            single_docs.append(filename)
        else:
            batch_scans.append(filename)
        
        print()
    
    print("=== SUMMARY ===")
    print(f"Total files analyzed: {len(analyses)}")
    print(f"Detected as single documents: {len(single_docs)}")
    print(f"Detected as batch scans: {len(batch_scans)}")
    
    if single_docs:
        print(f"\nSingle documents:")
        for filename in single_docs:
            print(f"  - {filename}")
    
    if batch_scans:
        print(f"\nBatch scans:")
        for filename in batch_scans:
            print(f"  - {filename}")
    
    print("\n=== VALIDATION QUESTIONS ===")
    print("Please review the above classifications and consider:")
    print("1. Are the 'single document' classifications correct?")
    print("2. Would any 'batch scan' files be better processed as single documents?")
    print("3. Are the confidence levels appropriate?")
    print("\nRemember: It's safer to classify as 'batch scan' than to incorrectly")
    print("classify as 'single document' and lose the verification workflow.")

def simulate_filenames():
    """Test detection on simulated filenames to verify pattern matching."""
    detector = get_detector()
    
    print("\n=== FILENAME PATTERN TESTING ===\n")
    
    test_cases = [
        # Should be detected as single documents
        ("invoice_2024_001.pdf", "single"),
        ("contract_lease_2024.pdf", "single"), 
        ("receipt_amazon_12345.pdf", "single"),
        ("report_quarterly_2024.pdf", "single"),
        ("letter_resignation_2024.pdf", "single"),
        
        # Should be detected as batch scans
        ("scan_20240325.pdf", "batch"),
        ("batch_documents_001.pdf", "batch"),
        ("scanned_papers_2024.pdf", "batch"),
        ("combined_march_2024.pdf", "batch"),
        ("archive_2024_q1.pdf", "batch"),
        
        # Ambiguous cases (should default to batch)
        ("document.pdf", "batch"),
        ("untitled.pdf", "batch"),
        ("misc_files.pdf", "batch"),
        ("random_name.pdf", "batch"),
    ]
    
    correct_predictions = 0
    
    for filename, expected in test_cases:
        hint = detector._analyze_filename(filename.replace('.pdf', ''))
        
        # Convert hint to expected format
        if hint == "single":
            predicted = "single"
        else:
            predicted = "batch"  # Default behavior
        
        correct = predicted == expected
        if correct:
            correct_predictions += 1
        
        status = "✓" if correct else "✗"
        print(f"{status} {filename:25} | Expected: {expected:6} | Predicted: {predicted:6} | Hint: {hint}")
    
    accuracy = correct_predictions / len(test_cases) * 100
    print(f"\nFilename Pattern Accuracy: {correct_predictions}/{len(test_cases)} ({accuracy:.1f}%)")

if __name__ == "__main__":
    print("Document Detection Validation Tool")
    print("=" * 40)
    
    # Test filename patterns
    simulate_filenames()
    
    # Test with real files if available
    test_detection_with_sample_files()
    
    print("\n" + "=" * 40)
    print("Testing complete!")
    print("\nNext steps:")
    print("1. Review the classifications above")
    print("2. Adjust detection thresholds if needed")
    print("3. Test with your actual 278 PDFs (small sample first)")
    print("4. The system will show you a preview before processing")
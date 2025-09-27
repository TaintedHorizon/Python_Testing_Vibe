#!/usr/bin/env python3
"""
Manual OCR re-run for a specific document.

This script re-runs OCR on a specific PDF and updates the database with the results.
"""

import sys
import os
import sqlite3
import logging

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from doc_processor.database import get_db_connection
from doc_processor.processing import create_searchable_pdf

def rerun_ocr_for_document(filename: str):
    """
    Re-run OCR for a specific document and update the database.
    """
    logging.basicConfig(level=logging.INFO)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get document details
        cursor.execute("""
            SELECT id, original_pdf_path, searchable_pdf_path 
            FROM single_documents 
            WHERE original_filename = ?
        """, (filename,))
        
        result = cursor.fetchone()
        if not result:
            print(f"Document {filename} not found in database")
            return
        
        doc_id, original_path, searchable_path = result
        
        print(f"Re-running OCR for {filename}...")
        print(f"Original PDF: {original_path}")
        print(f"Searchable PDF: {searchable_path}")
        
        if not os.path.exists(original_path):
            print(f"Error: Original PDF not found at {original_path}")
            return
        
        # Re-run OCR
        ocr_text, ocr_confidence, ocr_status = create_searchable_pdf(
            original_path, searchable_path
        )
        
        print(f"OCR Status: {ocr_status}")
        print(f"OCR Confidence: {ocr_confidence}")
        print(f"OCR Text Length: {len(ocr_text) if ocr_text else 0}")
        
        if ocr_text:
            print(f"First 200 characters of OCR text:")
            print(ocr_text[:200] + "..." if len(ocr_text) > 200 else ocr_text)
        
        # Update the database
        cursor.execute("""
            UPDATE single_documents SET
                ocr_text = ?,
                ocr_confidence_avg = ?
            WHERE id = ?
        """, (ocr_text, ocr_confidence, doc_id))
        
        conn.commit()
        print(f"✓ Successfully updated OCR data for {filename}")
        
        # Now re-run AI analysis with the new OCR text
        if ocr_text:
            print(f"\nRe-running AI analysis with new OCR text...")
            from doc_processor.processing import _get_ai_suggestions_for_document
            
            # Get file info
            cursor.execute("""
                SELECT page_count, file_size_bytes 
                FROM single_documents 
                WHERE id = ?
            """, (doc_id,))
            page_count, file_size_bytes = cursor.fetchone()
            file_size_mb = file_size_bytes / (1024 * 1024) if file_size_bytes else 0
            
            ai_category, ai_filename, ai_confidence, ai_summary = _get_ai_suggestions_for_document(
                ocr_text, filename, page_count or 1, file_size_mb
            )
            
            # Update AI suggestions
            cursor.execute("""
                UPDATE single_documents SET
                    ai_suggested_category = ?,
                    ai_suggested_filename = ?,
                    ai_confidence = ?,
                    ai_summary = ?
                WHERE id = ?
            """, (ai_category, ai_filename, ai_confidence, ai_summary, doc_id))
            
            conn.commit()
            
            print(f"✓ AI Analysis Results:")
            print(f"  Category: {ai_category}")
            print(f"  Filename: {ai_filename}")
            print(f"  Confidence: {ai_confidence:.2f}")
            print(f"  Summary: {ai_summary}")
        
    except Exception as e:
        print(f"Error processing {filename}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python rerun_ocr_for_document.py <filename>")
        print("Example: python rerun_ocr_for_document.py Kids_000287.pdf")
        sys.exit(1)
    
    filename = sys.argv[1]
    rerun_ocr_for_document(filename)
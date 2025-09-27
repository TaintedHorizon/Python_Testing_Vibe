#!/usr/bin/env python3
"""
Batch OCR re-run for all documents in a batch.

This script re-runs OCR on all documents in a batch that have missing or failed OCR.
"""

import sys
import os
import sqlite3
import logging

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from doc_processor.database import get_db_connection
from doc_processor.processing import create_searchable_pdf, _get_ai_suggestions_for_document

def rerun_ocr_for_batch(batch_id: int):
    """
    Re-run OCR for all documents in a batch that need it.
    """
    logging.basicConfig(level=logging.INFO)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get all documents in the batch with missing or low confidence OCR
        cursor.execute("""
            SELECT id, original_filename, original_pdf_path, searchable_pdf_path, ocr_confidence_avg, page_count, file_size_bytes
            FROM single_documents 
            WHERE batch_id = ? AND (ocr_confidence_avg IS NULL OR ocr_confidence_avg < 10)
            ORDER BY original_filename
        """, (batch_id,))
        
        documents = cursor.fetchall()
        if not documents:
            print(f"No documents need OCR re-processing in batch {batch_id}")
            return
        
        print(f"Re-running OCR for {len(documents)} documents in batch {batch_id}...")
        print("=" * 80)
        
        for doc_id, filename, original_path, searchable_path, old_ocr_conf, page_count, file_size_bytes in documents:
            print(f"\nProcessing {filename}...")
            print(f"  Original OCR Confidence: {old_ocr_conf}")
            
            if not os.path.exists(original_path):
                print(f"  ❌ Error: Original PDF not found at {original_path}")
                continue
            
            # Re-run OCR
            ocr_text, ocr_confidence, ocr_status = create_searchable_pdf(
                original_path, searchable_path
            )
            
            print(f"  ✓ New OCR Confidence: {ocr_confidence:.1f}%")
            print(f"  ✓ OCR Text Length: {len(ocr_text) if ocr_text else 0}")
            
            # Update OCR data in database
            cursor.execute("""
                UPDATE single_documents SET
                    ocr_text = ?,
                    ocr_confidence_avg = ?
                WHERE id = ?
            """, (ocr_text, ocr_confidence, doc_id))
            
            # Re-run AI analysis with the new OCR text
            if ocr_text:
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
                
                print(f"  ✓ New AI Category: {ai_category}")
                print(f"  ✓ New AI Filename: {ai_filename}")
                print(f"  ✓ New AI Confidence: {ai_confidence:.2f}")
            else:
                print(f"  ⚠️ No text extracted - AI analysis skipped")
            
            conn.commit()
        
        print(f"\n✅ Successfully processed all documents in batch {batch_id}")
        
    except Exception as e:
        print(f"Error processing batch {batch_id}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python rerun_ocr_for_batch.py <batch_id>")
        print("Example: python rerun_ocr_for_batch.py 2")
        sys.exit(1)
    
    try:
        batch_id = int(sys.argv[1])
        rerun_ocr_for_batch(batch_id)
    except ValueError:
        print("Error: batch_id must be an integer")
        sys.exit(1)
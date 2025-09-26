#!/usr/bin/env python3
"""
Regenerate AI suggestions for existing single documents.

This script re-analyzes existing documents in the single_documents table
to generate proper AI-based filenames using the enhanced AI analysis.
"""

import sys
import os
import sqlite3
import logging

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from doc_processor.database import get_db_connection
from doc_processor.processing import _get_ai_suggestions_for_document

def regenerate_ai_suggestions_for_batch(batch_id: int):
    """
    Regenerate AI suggestions for all documents in a batch.
    """
    logging.basicConfig(level=logging.INFO)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get all documents in the batch
        cursor.execute("""
            SELECT id, original_filename, ocr_text, page_count, file_size_bytes 
            FROM single_documents 
            WHERE batch_id = ?
        """, (batch_id,))
        
        documents = cursor.fetchall()
        if not documents:
            print(f"No documents found in batch {batch_id}")
            return
        
        print(f"Regenerating AI suggestions for {len(documents)} documents in batch {batch_id}...")
        
        for doc_id, filename, ocr_text, page_count, file_size_bytes in documents:
            print(f"\nProcessing {filename}...")
            
            # Convert file size back to MB
            file_size_mb = file_size_bytes / (1024 * 1024) if file_size_bytes else 0
            
            # Get new AI suggestions
            ai_category, ai_filename, ai_confidence, ai_summary = _get_ai_suggestions_for_document(
                ocr_text or "", filename, page_count or 1, file_size_mb
            )
            
            # Update the database
            cursor.execute("""
                UPDATE single_documents SET
                    ai_suggested_category = ?,
                    ai_suggested_filename = ?,
                    ai_confidence = ?,
                    ai_summary = ?
                WHERE id = ?
            """, (ai_category, ai_filename, ai_confidence, ai_summary, doc_id))
            
            print(f"  ✓ Category: {ai_category}")
            print(f"  ✓ Filename: {ai_filename}")
            print(f"  ✓ Confidence: {ai_confidence:.2f}")
            print(f"  ✓ Summary: {ai_summary}")
        
        conn.commit()
        print(f"\n✓ Successfully regenerated AI suggestions for batch {batch_id}")
        
    except Exception as e:
        print(f"Error regenerating AI suggestions: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python regenerate_ai_suggestions.py <batch_id>")
        sys.exit(1)
    
    try:
        batch_id = int(sys.argv[1])
        regenerate_ai_suggestions_for_batch(batch_id)
    except ValueError:
        print("Error: batch_id must be an integer")
        sys.exit(1)
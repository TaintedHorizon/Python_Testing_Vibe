#!/usr/bin/env python3
"""
Reset Batch 4 for Fresh Processing

Resets batch 4 to start fresh while preserving the documents.
This allows testing the full smart processing workflow with caching.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import sqlite3
from contextlib import contextmanager

@contextmanager
def database_connection():
    """Database connection for reset operation."""
    db_path = os.path.join(os.path.dirname(__file__), 'documents.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def reset_batch_4_for_fresh_start():
    """
    Reset batch 4 to start fresh processing from the beginning.
    This clears all processing results but keeps the original files.
    """
    print("🔄 Resetting Batch 4 for Fresh Start...")
    
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            
            # Check current state
            cursor.execute("""
                SELECT COUNT(*) as total,
                       COUNT(CASE WHEN status = 'ready_for_manipulation' THEN 1 END) as completed,
                       COUNT(CASE WHEN ocr_text IS NOT NULL THEN 1 END) as has_ocr,
                       COUNT(CASE WHEN ai_suggested_category IS NOT NULL THEN 1 END) as has_ai
                FROM single_documents WHERE batch_id = 4
            """)
            stats = cursor.fetchone()
            
            if stats:
                total, completed, has_ocr, has_ai = stats
                print(f"📊 Current Batch 4 State:")
                print(f"  Total Documents: {total}")
                print(f"  Completed: {completed}")
                print(f"  Has OCR: {has_ocr}")
                print(f"  Has AI Analysis: {has_ai}")
                
                if total == 0:
                    print("❌ No documents found in batch 4")
                    return False
            
            # Clear all processing results to start fresh
            cursor.execute("""
                UPDATE single_documents SET
                    ocr_text = NULL,
                    ocr_confidence_avg = NULL,
                    ai_suggested_category = NULL,
                    ai_suggested_filename = NULL,
                    ai_confidence = NULL,
                    ai_summary = NULL,
                    final_category = NULL,
                    final_filename = NULL,
                    status = 'processing',
                    searchable_pdf_path = NULL,
                    markdown_path = NULL,
                    processed_at = NULL
                WHERE batch_id = 4
            """)
            
            # Reset batch status to processing
            cursor.execute("UPDATE batches SET status = 'processing' WHERE id = 4")
            
            conn.commit()
            
            print(f"\n✅ Batch 4 Reset Complete!")
            print(f"  🧹 Cleared all OCR results")
            print(f"  🧹 Cleared all AI analysis")
            print(f"  🧹 Reset all document statuses to 'processing'")
            print(f"  🧹 Reset batch status to 'processing'")
            print(f"  📁 Original PDF files preserved")
            
            # Show what will be processed
            cursor.execute("""
                SELECT id, original_filename, original_pdf_path 
                FROM single_documents 
                WHERE batch_id = 4 
                ORDER BY original_filename
            """)
            docs = cursor.fetchall()
            
            print(f"\n📄 Documents ready for fresh processing:")
            for doc in docs:
                doc_id, filename, pdf_path = doc
                exists = "✅" if pdf_path and os.path.exists(pdf_path) else "❌"
                print(f"  {exists} {filename}")
            
    except Exception as e:
        print(f"❌ Error during reset: {e}")
        return False
    
    return True


def verify_fresh_start():
    """
    Verify that batch 4 is ready for fresh processing.
    """
    print(f"\n🔍 Verifying Fresh Start Setup...")
    
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            
            # Check batch status
            cursor.execute("SELECT status FROM batches WHERE id = 4")
            batch_status = cursor.fetchone()
            
            if batch_status and batch_status[0] == 'processing':
                print("✅ Batch 4 status: processing")
            else:
                print(f"⚠️  Batch 4 status: {batch_status[0] if batch_status else 'not found'}")
            
            # Check document states
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing,
                    COUNT(CASE WHEN ocr_text IS NULL THEN 1 END) as no_ocr,
                    COUNT(CASE WHEN ai_suggested_category IS NULL THEN 1 END) as no_ai
                FROM single_documents WHERE batch_id = 4
            """)
            doc_stats = cursor.fetchone()
            
            if doc_stats:
                total, processing, no_ocr, no_ai = doc_stats
                
                if total == processing == no_ocr == no_ai:
                    print(f"✅ All {total} documents ready for fresh processing")
                else:
                    print(f"⚠️  Document states: {processing}/{total} processing, {no_ocr}/{total} no OCR, {no_ai}/{total} no AI")
                    
    except Exception as e:
        print(f"❌ Error verifying setup: {e}")


if __name__ == "__main__":
    print("🚨 BATCH 4 FRESH START RESET")
    print("=" * 40)
    print("This will clear all processing results and start batch 4 from scratch.")
    print("Original PDF files will be preserved.")
    print("")
    
    confirm = input("Continue with reset? (y/N): ").strip().lower()
    
    if confirm == 'y':
        success = reset_batch_4_for_fresh_start()
        
        if success:
            verify_fresh_start()
            print(f"\n🎯 READY FOR TESTING:")
            print("1. Restart Flask server")
            print("2. Go to Smart Processing")
            print("3. System will find batch 4 and process from beginning")
            print("4. Watch the new caching system work!")
        else:
            print("❌ Reset failed - check errors above")
    else:
        print("❌ Reset cancelled")
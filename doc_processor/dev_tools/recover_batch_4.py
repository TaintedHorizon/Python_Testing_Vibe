#!/usr/bin/env python3
"""
Batch Recovery Script

Recovers batch 4 from phantom batches and sets up proper resumability.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import sqlite3
from contextlib import contextmanager

@contextmanager
def database_connection():
    """Database connection for recovery."""
    db_path = os.path.join(os.path.dirname(__file__), 'documents.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def recover_batch_4():
    """
    Recover the original batch 4 by consolidating phantom batches.
    """
    print("🔧 Starting Batch 4 Recovery...")
    
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            
            # Check current state
            cursor.execute("SELECT id, status FROM batches WHERE id >= 4 ORDER BY id")
            existing_batches = cursor.fetchall()
            print(f"Current batches >= 4: {[(row[0], row[1]) for row in existing_batches]}")
            
            # Get documents from phantom batches
            cursor.execute("""
                SELECT id, batch_id, original_filename, status 
                FROM single_documents 
                WHERE batch_id >= 4 
                ORDER BY batch_id, id
            """)
            orphaned_docs = cursor.fetchall()
            print(f"Documents in phantom batches: {len(orphaned_docs)}")
            
            if not orphaned_docs:
                print("✅ No documents to recover")
                return
            
            # Create batch 4 (or update existing)
            cursor.execute("SELECT id FROM batches WHERE id = 4")
            batch_4_exists = cursor.fetchone()
            
            if not batch_4_exists:
                cursor.execute("INSERT INTO batches (id, status) VALUES (4, 'processing')")
                print("✨ Created new batch 4")
            else:
                cursor.execute("UPDATE batches SET status = 'processing' WHERE id = 4")
                print("🔄 Updated existing batch 4 to processing status")
            
            # Move all documents to batch 4
            moved_count = 0
            for doc in orphaned_docs:
                doc_id, old_batch_id, filename, status = doc
                cursor.execute("""
                    UPDATE single_documents 
                    SET batch_id = 4 
                    WHERE id = ?
                """, (doc_id,))
                moved_count += 1
                print(f"  📁 Moved {filename} from batch {old_batch_id} to batch 4")
            
            # Delete phantom batches (5, 6, etc.)
            cursor.execute("DELETE FROM batches WHERE id > 4")
            deleted_batches = cursor.rowcount
            
            conn.commit()
            
            print(f"\n✅ Recovery Complete!")
            print(f"  📄 Moved {moved_count} documents to batch 4")
            print(f"  🗑️  Deleted {deleted_batches} phantom batches")
            print(f"  🎯 Batch 4 status: processing (ready for resumable processing)")
            
            # Show final state
            cursor.execute("""
                SELECT COUNT(*) as doc_count,
                       COUNT(CASE WHEN status = 'ready_for_manipulation' THEN 1 END) as completed,
                       COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing,
                       COUNT(CASE WHEN ocr_text IS NOT NULL THEN 1 END) as has_ocr,
                       COUNT(CASE WHEN ai_suggested_category IS NOT NULL THEN 1 END) as has_ai
                FROM single_documents WHERE batch_id = 4
            """)
            stats = cursor.fetchone()
            
            if stats:
                total, completed, processing, has_ocr, has_ai = stats
                print(f"\n📊 Batch 4 Recovery Stats:")
                print(f"  Total Documents: {total}")
                print(f"  Completed: {completed}")
                print(f"  Processing: {processing}")
                print(f"  Has OCR: {has_ocr}")
                print(f"  Has AI Analysis: {has_ai}")
                
                if completed > 0:
                    print(f"  🎉 {completed} documents already completed (will use cached results!)")
                if processing > 0:
                    print(f"  🔄 {processing} documents need completion")
                
    except Exception as e:
        print(f"❌ Error during recovery: {e}")
        return False
    
    return True


def verify_batch_guard():
    """
    Verify that batch guard will work properly going forward.
    """
    print(f"\n🛡️  Verifying Batch Guard Setup...")
    
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            
            # Check for multiple processing batches
            cursor.execute("""
                SELECT COUNT(*) FROM batches WHERE status = 'processing'
            """)
            processing_count = cursor.fetchone()[0]
            
            if processing_count == 1:
                print("✅ Exactly 1 processing batch (batch 4)")
            else:
                print(f"⚠️  Found {processing_count} processing batches - should be 1")
            
            # Check batch guard will find batch 4
            cursor.execute("""
                SELECT id FROM batches 
                WHERE status = 'processing' 
                ORDER BY id DESC 
                LIMIT 1
            """)
            result = cursor.fetchone()
            
            if result and result[0] == 4:
                print("✅ Batch guard will correctly find batch 4")
            else:
                print(f"⚠️  Batch guard will find batch {result[0] if result else 'None'}")
                
    except Exception as e:
        print(f"❌ Error verifying batch guard: {e}")


if __name__ == "__main__":
    print("🚨 BATCH 4 RECOVERY OPERATION")
    print("=" * 40)
    
    success = recover_batch_4()
    
    if success:
        verify_batch_guard()
        print(f"\n🎯 NEXT STEPS:")
        print("1. Restart Flask server")
        print("2. Go to Smart Processing")
        print("3. Batch 4 will resume where it left off")
        print("4. No more phantom batches will be created!")
    else:
        print("❌ Recovery failed - check errors above")
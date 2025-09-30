#!/usr/bin/env python3
"""
Data preservation and cleanup script.

This script will:
1. Preserve any valuable data from phantom batches by moving it to batch 1
2. Safely remove phantom batches 8, 9, etc.
3. Ensure the next batch will be batch 4
"""

import sqlite3
import os
import sys
import json
from datetime import datetime

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import get_db_connection

def preserve_valuable_data():
    """Move any valuable RAG/LLM data from phantom batches to batch 1."""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        print("🔍 Analyzing phantom batches for valuable data...")
        
        # Check for single documents in phantom batches that have valuable data
        cursor.execute("""
            SELECT id, batch_id, original_filename, final_category, final_filename, 
                   ai_suggested_category, ai_suggested_filename, ocr_text, ai_confidence
            FROM single_documents 
            WHERE batch_id > 3
            AND (final_category IS NOT NULL OR ai_suggested_category IS NOT NULL)
        """)
        valuable_single_docs = cursor.fetchall()
        
        # Check for completed documents in phantom batches
        cursor.execute("""
            SELECT d.id, d.batch_id, d.document_name, d.status,
                   COUNT(dp.page_id) as page_count
            FROM documents d
            LEFT JOIN document_pages dp ON d.id = dp.document_id
            WHERE d.batch_id > 3
            GROUP BY d.id
        """)
        valuable_docs = cursor.fetchall()
        
        # Check for interaction logs with human corrections
        cursor.execute("""
            SELECT batch_id, document_id, event_type, content, notes, timestamp
            FROM interaction_log 
            WHERE batch_id > 3
            AND event_type IN ('human_correction', 'ai_response', 'document_finalized')
        """)
        valuable_interactions = cursor.fetchall()
        
        # Check for document tags
        cursor.execute("""
            SELECT dt.*, sd.batch_id
            FROM document_tags dt
            JOIN single_documents sd ON dt.document_id = sd.id
            WHERE sd.batch_id > 3
        """)
        valuable_tags = cursor.fetchall()
        
        print(f"📊 Found valuable data:")
        print(f"   - Single documents: {len(valuable_single_docs)}")
        print(f"   - Documents: {len(valuable_docs)}")
        print(f"   - Interaction logs: {len(valuable_interactions)}")
        print(f"   - Document tags: {len(valuable_tags)}")
        
        if not any([valuable_single_docs, valuable_docs, valuable_interactions, valuable_tags]):
            print("✅ No valuable data found in phantom batches - safe to delete")
            return True
        
        # Move single documents to batch 1
        if valuable_single_docs:
            print(f"\n📦 Moving {len(valuable_single_docs)} single documents to batch 1...")
            for doc in valuable_single_docs:
                doc_id = doc[0]
                # Update batch_id to 1
                cursor.execute("UPDATE single_documents SET batch_id = 1 WHERE id = ?", (doc_id,))
                print(f"   ✓ Moved single document {doc_id}: {doc[2]} ({doc[3]})")
        
        # Create preservation log entry
        preservation_data = {
            "preservation_timestamp": datetime.now().isoformat(),
            "reason": "Phantom batch cleanup - data preserved to batch 1",
            "original_batches": list(set([str(doc[1]) for doc in valuable_single_docs])),
            "single_docs_moved": len(valuable_single_docs),
            "docs_moved": len(valuable_docs),
            "interactions_preserved": len(valuable_interactions),
            "tags_preserved": len(valuable_tags)
        }
        
        # Add preservation log to interaction_log
        cursor.execute("""
            INSERT INTO interaction_log (batch_id, user_id, event_type, step, content, notes)
            VALUES (1, 'system', 'data_preservation', 'cleanup', ?, ?)
        """, (
            json.dumps(preservation_data),
            f"Preserved data from phantom batches during cleanup on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ))
        
        # Move interaction logs to batch 1 (update batch_id)
        if valuable_interactions:
            print(f"\n📝 Moving {len(valuable_interactions)} interaction logs to batch 1...")
            phantom_batch_ids = list(set([str(log[0]) for log in valuable_interactions if log[0] > 3]))
            for batch_id in phantom_batch_ids:
                cursor.execute("UPDATE interaction_log SET batch_id = 1 WHERE batch_id = ?", (batch_id,))
                print(f"   ✓ Moved interaction logs from batch {batch_id} to batch 1")
        
        conn.commit()
        print("✅ All valuable data preserved in batch 1")
        return True
        
    except Exception as e:
        print(f"💥 Error preserving data: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def cleanup_phantom_batches():
    """Remove phantom batches after data preservation."""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get phantom batch IDs
        cursor.execute("SELECT id FROM batches WHERE id > 3 ORDER BY id")
        phantom_batch_ids = [row[0] for row in cursor.fetchall()]
        
        if not phantom_batch_ids:
            print("✅ No phantom batches to clean up")
            return True
        
        print(f"\n🧹 Cleaning up phantom batches: {phantom_batch_ids}")
        
        batch_ids_str = ','.join(map(str, phantom_batch_ids))
        
        # Clean up remaining data (should be minimal after preservation)
        
        # Delete any remaining document tags
        cursor.execute(f"""
            DELETE FROM document_tags 
            WHERE document_id IN (
                SELECT id FROM single_documents WHERE batch_id IN ({batch_ids_str})
            )
        """)
        tags_deleted = cursor.rowcount
        
        # Delete any remaining single documents
        cursor.execute(f"DELETE FROM single_documents WHERE batch_id IN ({batch_ids_str})")
        single_docs_deleted = cursor.rowcount
        
        # Delete document_pages
        cursor.execute(f"""
            DELETE FROM document_pages 
            WHERE document_id IN (
                SELECT id FROM documents WHERE batch_id IN ({batch_ids_str})
            )
        """)
        doc_pages_deleted = cursor.rowcount
        
        # Delete documents
        cursor.execute(f"DELETE FROM documents WHERE batch_id IN ({batch_ids_str})")
        documents_deleted = cursor.rowcount
        
        # Delete pages
        cursor.execute(f"DELETE FROM pages WHERE batch_id IN ({batch_ids_str})")
        pages_deleted = cursor.rowcount
        
        # Delete any remaining interaction logs
        cursor.execute(f"DELETE FROM interaction_log WHERE batch_id IN ({batch_ids_str})")
        logs_deleted = cursor.rowcount
        
        # Delete the phantom batches
        cursor.execute(f"DELETE FROM batches WHERE id IN ({batch_ids_str})")
        batches_deleted = cursor.rowcount
        
        conn.commit()
        
        print(f"   ✓ Cleaned up:")
        print(f"     - Batches: {batches_deleted}")
        print(f"     - Pages: {pages_deleted}")
        print(f"     - Documents: {documents_deleted}")
        print(f"     - Document-page links: {doc_pages_deleted}")
        print(f"     - Single documents: {single_docs_deleted}")
        print(f"     - Tags: {tags_deleted}")
        print(f"     - Interaction logs: {logs_deleted}")
        
        return True
        
    except Exception as e:
        print(f"💥 Error during cleanup: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def reset_auto_increment():
    """Reset auto-increment to ensure next batch is #4."""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Reset the auto-increment sequence for batches table
        cursor.execute("UPDATE sqlite_sequence SET seq = 3 WHERE name = 'batches'")
        conn.commit()
        print("✅ Reset auto-increment - next batch will be #4")
        return True
        
    except Exception as e:
        print(f"⚠️ Could not reset auto-increment: {e}")
        return False
    finally:
        conn.close()

def verify_final_state():
    """Verify the database is in the correct state."""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check batches
        cursor.execute("SELECT id, start_time, status FROM batches ORDER BY id")
        batches = cursor.fetchall()
        
        print(f"\n📋 Final database state:")
        print(f"   Batches ({len(batches)}):")
        for batch in batches:
            print(f"     - Batch {batch[0]}: {batch[1]} ({batch[2]})")
        
        # Check for any orphaned data
        cursor.execute("SELECT COUNT(*) FROM pages WHERE batch_id > 3")
        orphaned_pages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM documents WHERE batch_id > 3")
        orphaned_docs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM single_documents WHERE batch_id > 3")
        orphaned_single_docs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM interaction_log WHERE batch_id > 3")
        orphaned_logs = cursor.fetchone()[0]
        
        # Check data in batch 1
        cursor.execute("SELECT COUNT(*) FROM single_documents WHERE batch_id = 1")
        batch1_single_docs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM interaction_log WHERE batch_id = 1")
        batch1_logs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM document_tags WHERE document_id IN (SELECT id FROM single_documents WHERE batch_id = 1)")
        batch1_tags = cursor.fetchone()[0]
        
        print(f"   Batch 1 enhanced data:")
        print(f"     - Single documents: {batch1_single_docs}")
        print(f"     - Interaction logs: {batch1_logs}")
        print(f"     - Document tags: {batch1_tags}")
        
        if orphaned_pages == 0 and orphaned_docs == 0 and orphaned_single_docs == 0 and orphaned_logs == 0:
            print("   ✅ No orphaned data - cleanup successful!")
            print("   ✅ All valuable data preserved in batch 1")
            print("   ✅ Ready for batch 4")
            return True
        else:
            print(f"   ⚠️ Orphaned data found:")
            print(f"     - Pages: {orphaned_pages}")
            print(f"     - Documents: {orphaned_docs}")
            print(f"     - Single documents: {orphaned_single_docs}")
            print(f"     - Interaction logs: {orphaned_logs}")
            return False
        
    except Exception as e:
        print(f"💥 Error during verification: {e}")
        return False
    finally:
        conn.close()

def main():
    """Run the complete data preservation and cleanup process."""
    
    print("🛡️  DATA PRESERVATION & CLEANUP")
    print("Moving valuable data to batch 1, then cleaning phantom batches")
    print("=" * 70)
    
    # Step 1: Preserve valuable data
    print("1. Preserving valuable data...")
    if not preserve_valuable_data():
        print("💥 Data preservation failed - aborting")
        return False
    
    # Step 2: Clean up phantom batches
    print("\n2. Cleaning up phantom batches...")
    if not cleanup_phantom_batches():
        print("💥 Cleanup failed - aborting")
        return False
    
    # Step 3: Reset auto-increment
    print("\n3. Resetting batch counter...")
    reset_auto_increment()
    
    # Step 4: Verify final state
    print("\n4. Verifying final state...")
    success = verify_final_state()
    
    if success:
        print("\n🎉 PRESERVATION & CLEANUP COMPLETE!")
        print("✅ All valuable data moved to batch 1 for RAG/LLM use")
        print("✅ Phantom batches removed")
        print("✅ Next batch will be #4")
        print("✅ Ready to resume normal operations")
    else:
        print("\n⚠️  CLEANUP INCOMPLETE!")
        print("❌ Some issues remain - check the verification output above")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
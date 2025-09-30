#!/usr/bin/env python3
"""
Emergency cleanup script to remove all batches above 3.

This script will:
1. Stop any running Flask processes
2. Clean up all batches with ID > 3
3. Clean up associated data (pages, documents, interaction logs, tags)
4. Reset the database to a clean state after batch 3
"""

import sqlite3
import os
import sys
import subprocess

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import get_db_connection

def stop_flask_processes():
    """Stop any running Flask processes."""
    try:
        # Find and kill Flask processes
        result = subprocess.run(['pkill', '-f', 'doc_processor.app'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Stopped Flask processes")
        else:
            print("ℹ No Flask processes found running")
    except Exception as e:
        print(f"⚠ Could not stop Flask processes: {e}")

def cleanup_phantom_batches():
    """Remove all batches with ID > 3 and their associated data."""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # First, check what batches exist above 3
        cursor.execute("SELECT id, start_time, status FROM batches WHERE id > 3 ORDER BY id")
        phantom_batches = cursor.fetchall()
        
        if not phantom_batches:
            print("✓ No phantom batches found - database is clean")
            return True
        
        print(f"🗑️ Found {len(phantom_batches)} phantom batches to remove:")
        for batch in phantom_batches:
            print(f"   - Batch {batch[0]}: {batch[1]} ({batch[2]})")
        
        # Get list of batch IDs to clean
        batch_ids = [str(batch[0]) for batch in phantom_batches]
        batch_ids_str = ','.join(batch_ids)
        
        print(f"\n🧹 Starting cleanup of batches: {batch_ids_str}")
        
        # Clean up in order to respect foreign key constraints
        
        # 1. Delete document tags for affected documents
        cursor.execute(f"""
            DELETE FROM document_tags 
            WHERE document_id IN (
                SELECT id FROM single_documents WHERE batch_id IN ({batch_ids_str})
            )
        """)
        tags_deleted = cursor.rowcount
        print(f"   ✓ Deleted {tags_deleted} document tags")
        
        # 2. Delete interaction logs
        cursor.execute(f"DELETE FROM interaction_log WHERE batch_id IN ({batch_ids_str})")
        logs_deleted = cursor.rowcount
        print(f"   ✓ Deleted {logs_deleted} interaction log entries")
        
        # 3. Delete single documents
        cursor.execute(f"DELETE FROM single_documents WHERE batch_id IN ({batch_ids_str})")
        single_docs_deleted = cursor.rowcount
        print(f"   ✓ Deleted {single_docs_deleted} single documents")
        
        # 4. Delete document_pages (junction table)
        cursor.execute(f"""
            DELETE FROM document_pages 
            WHERE document_id IN (
                SELECT id FROM documents WHERE batch_id IN ({batch_ids_str})
            )
        """)
        doc_pages_deleted = cursor.rowcount
        print(f"   ✓ Deleted {doc_pages_deleted} document-page associations")
        
        # 5. Delete documents
        cursor.execute(f"DELETE FROM documents WHERE batch_id IN ({batch_ids_str})")
        documents_deleted = cursor.rowcount
        print(f"   ✓ Deleted {documents_deleted} documents")
        
        # 6. Delete pages
        cursor.execute(f"DELETE FROM pages WHERE batch_id IN ({batch_ids_str})")
        pages_deleted = cursor.rowcount
        print(f"   ✓ Deleted {pages_deleted} pages")
        
        # 7. Finally, delete the phantom batches themselves
        cursor.execute(f"DELETE FROM batches WHERE id IN ({batch_ids_str})")
        batches_deleted = cursor.rowcount
        print(f"   ✓ Deleted {batches_deleted} phantom batches")
        
        # Commit all changes
        conn.commit()
        
        print(f"\n🎉 Cleanup complete! Removed all data for batches: {batch_ids_str}")
        print(f"📊 Summary:")
        print(f"   - Batches deleted: {batches_deleted}")
        print(f"   - Pages deleted: {pages_deleted}")
        print(f"   - Documents deleted: {documents_deleted}")
        print(f"   - Document-page associations deleted: {doc_pages_deleted}")
        print(f"   - Single documents deleted: {single_docs_deleted}")
        print(f"   - Interaction logs deleted: {logs_deleted}")
        print(f"   - Document tags deleted: {tags_deleted}")
        
        return True
        
    except Exception as e:
        print(f"💥 Error during cleanup: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def verify_cleanup():
    """Verify that cleanup was successful."""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check remaining batches
        cursor.execute("SELECT id, start_time, status FROM batches ORDER BY id")
        remaining_batches = cursor.fetchall()
        
        print(f"\n📋 Database state after cleanup:")
        print(f"   Remaining batches: {len(remaining_batches)}")
        for batch in remaining_batches:
            print(f"   - Batch {batch[0]}: {batch[1]} ({batch[2]})")
        
        # Check for any orphaned data
        cursor.execute("SELECT COUNT(*) FROM pages WHERE batch_id > 3")
        orphaned_pages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM documents WHERE batch_id > 3")
        orphaned_docs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM single_documents WHERE batch_id > 3")
        orphaned_single_docs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM interaction_log WHERE batch_id > 3")
        orphaned_logs = cursor.fetchone()[0]
        
        if orphaned_pages == 0 and orphaned_docs == 0 and orphaned_single_docs == 0 and orphaned_logs == 0:
            print("   ✅ No orphaned data found - cleanup was successful!")
            return True
        else:
            print(f"   ⚠️ Found orphaned data:")
            print(f"      - Pages: {orphaned_pages}")
            print(f"      - Documents: {orphaned_docs}")
            print(f"      - Single documents: {orphaned_single_docs}")
            print(f"      - Interaction logs: {orphaned_logs}")
            return False
        
    except Exception as e:
        print(f"💥 Error during verification: {e}")
        return False
    finally:
        conn.close()

def main():
    """Run the complete cleanup process."""
    
    print("🚨 EMERGENCY CLEANUP: Removing phantom batches above 3")
    print("=" * 60)
    
    # Step 1: Stop Flask processes
    print("1. Stopping Flask processes...")
    stop_flask_processes()
    
    # Step 2: Clean up phantom batches
    print("\n2. Cleaning up phantom batches...")
    cleanup_success = cleanup_phantom_batches()
    
    if not cleanup_success:
        print("💥 Cleanup failed - exiting")
        return False
    
    # Step 3: Verify cleanup
    print("\n3. Verifying cleanup...")
    verify_success = verify_cleanup()
    
    if verify_success:
        print("\n🎉 CLEANUP COMPLETE!")
        print("✅ Database is now clean with only batches 1-3")
        print("✅ All phantom batch data has been removed")
        print("✅ Ready to resume normal operations")
        return True
    else:
        print("\n⚠️ CLEANUP INCOMPLETE!")
        print("❌ Some orphaned data may remain")
        print("❌ Manual intervention may be required")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
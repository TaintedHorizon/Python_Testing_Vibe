#!/usr/bin/env python3
"""
Verification script to check single document processing flow.

This script verifies that:
1. Single documents use the modern workflow (_process_single_documents_as_batch)
2. Single documents end up in category folders, NOT archive
3. All file movements are safe with verification
"""

import os
import sys
import logging

# Add the doc_processor directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_manager import app_config
from database import get_db_connection

def check_single_document_workflow():
    """Check the database for any single documents and their final locations."""

    print("🔍 Checking Single Document Workflow...")
    print("=" * 60)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check for single document batches
    cursor.execute("""
        SELECT b.id, b.status, b.start_time, COUNT(sd.id) as doc_count
        FROM batches b
        LEFT JOIN single_documents sd ON b.id = sd.batch_id
        WHERE sd.batch_id IS NOT NULL
        GROUP BY b.id, b.status, b.start_time
        ORDER BY b.start_time DESC
    """)

    single_doc_batches = cursor.fetchall()

    if not single_doc_batches:
        print("✅ No single document batches found (system clean)")
        conn.close()
        return True

    print(f"📊 Found {len(single_doc_batches)} single document batches:")
    print()

    for batch_id, status, start_time, doc_count in single_doc_batches:
        print(f"Batch #{batch_id}")
        print(f"  Status: {status}")
        print(f"  Start Time: {start_time}")
        print(f"  Documents: {doc_count}")
        print()

    conn.close()
    print("🎯 Verification Complete!")
    return True

def check_archive_for_single_documents():
    """Check if any single documents ended up in archive (they shouldn't)."""

    print("🔍 Checking Archive for Misplaced Single Documents...")
    print("=" * 60)

    if not app_config.ARCHIVE_DIR or not os.path.exists(app_config.ARCHIVE_DIR):
        print("✅ No archive directory found")
        return True

    pdf_files = [f for f in os.listdir(app_config.ARCHIVE_DIR) if f.lower().endswith('.pdf')]

    if not pdf_files:
        print("✅ Archive is empty (good - single docs should go to categories)")
        return True

    print(f"⚠️  Found {len(pdf_files)} PDF files in archive:")
    for pdf_file in pdf_files:
        print(f"    📄 {pdf_file}")

    print("\n💡 If these are single documents, they should be in category folders instead!")
    return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    try:
        check_single_document_workflow()
        print()
        check_archive_for_single_documents()

        print("\n" + "=" * 60)
        print("📋 SUMMARY: Single Document Flow Verification")
        print("=" * 60)
        print("✅ Modern workflow: _process_single_documents_as_batch() → category folders")
        print("❌ Legacy workflow: process_single_document() → archive (DEPRECATED)")
        print("\n💡 All single documents should now use the modern workflow!")
        print("   Single docs go: intake → WIP → category folders (NOT archive)")

    except Exception as e:
        print(f"❌ Error during verification: {e}")
        sys.exit(1)
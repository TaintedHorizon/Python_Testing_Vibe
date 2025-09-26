#!/usr/bin/env python3
"""
Consolidate malformed single-document batches into one proper batch.

This script fixes the issue where smart processing created individual batches 
for each single document instead of grouping them into one batch.

It will:
1. Create a new batch for consolidated single documents
2. Move all documents from batches 5-33 to the new batch
3. Update batch status to pending_verification
4. Mark old batches as consolidated/hidden
"""

import sqlite3
import logging
import sys
import os
from datetime import datetime

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config_manager import app_config
from database import get_db_connection

def consolidate_malformed_batches():
    """
    Consolidate single-document batches into one proper batch.
    """
    logging.basicConfig(level=logging.INFO)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Find all malformed single-document batches (typically 5-33+)
        malformed_batches = []
        
        # Check batches 3-50 to catch any malformed ones
        for batch_id in range(3, 51):
            # Count documents and pages
            doc_count = cursor.execute('SELECT COUNT(*) FROM documents WHERE batch_id = ?', (batch_id,)).fetchone()[0]
            page_count = cursor.execute('SELECT COUNT(*) FROM pages WHERE batch_id = ?', (batch_id,)).fetchone()[0]
            
            # If it has exactly 1 document and 0 pages, it's likely a malformed single-doc batch
            if doc_count == 1 and page_count == 0:
                malformed_batches.append(batch_id)
                
        print(f"Found {len(malformed_batches)} malformed single-document batches: {malformed_batches}")
        
        if not malformed_batches:
            print("No malformed batches found. Nothing to consolidate.")
            return
        
        # Get all documents from malformed batches
        documents_to_move = []
        for batch_id in malformed_batches:
            docs = cursor.execute(
                'SELECT id, document_name, processing_strategy, original_file_path FROM documents WHERE batch_id = ?',
                (batch_id,)
            ).fetchall()
            documents_to_move.extend([(doc[0], doc[1], doc[2], doc[3], batch_id) for doc in docs])
        
        print(f"Found {len(documents_to_move)} documents to consolidate:")
        for doc_id, doc_name, strategy, path, old_batch in documents_to_move:
            print(f"  Doc {doc_id}: {doc_name} (from batch {old_batch})")
        
        # Create new consolidated batch
        cursor.execute(
            "INSERT INTO batches (status, start_time) VALUES (?, ?)",
            (app_config.STATUS_PENDING_VERIFICATION, datetime.now())
        )
        new_batch_id = cursor.lastrowid
        conn.commit()
        
        print(f"Created new consolidated batch: {new_batch_id}")
        
        # Move all documents to the new batch
        for doc_id, doc_name, strategy, path, old_batch in documents_to_move:
            cursor.execute(
                'UPDATE documents SET batch_id = ? WHERE id = ?',
                (new_batch_id, doc_id)
            )
            print(f"  Moved document {doc_id} ({doc_name}) to batch {new_batch_id}")
        
        # Mark old batches as consolidated (we'll add a note to identify them)
        for batch_id in malformed_batches:
            cursor.execute(
                'UPDATE batches SET status = ? WHERE id = ?',
                ('consolidated_into_' + str(new_batch_id), batch_id)
            )
        
        conn.commit()
        
        print(f"\\nSuccess! Consolidated {len(documents_to_move)} documents into batch {new_batch_id}")
        print(f"Old batches {malformed_batches} marked as consolidated")
        print(f"New batch {new_batch_id} is ready for verification workflow")
        
    except Exception as e:
        print(f"Error during consolidation: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    consolidate_malformed_batches()
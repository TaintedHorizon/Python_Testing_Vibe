#!/usr/bin/env python3
"""
Add single_documents table for the improved single document workflow.

This creates a new table to track single documents through the streamlined workflow:
OCR → Reassemble searchable PDF → AI suggestions → Finalize/Export
"""

import sqlite3
import logging
import sys
import os

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import get_db_connection

def add_single_documents_table():
    """
    Add the single_documents table to the database.
    """
    logging.basicConfig(level=logging.INFO)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if table already exists
        result = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='single_documents'"
        ).fetchone()
        
        if result:
            print("single_documents table already exists. Skipping creation.")
            return
        
        # Create the single_documents table
        cursor.execute("""
            CREATE TABLE single_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                original_pdf_path TEXT,
                searchable_pdf_path TEXT,
                markdown_path TEXT,
                page_count INTEGER NOT NULL,
                file_size_bytes INTEGER,
                ocr_text TEXT,
                ocr_confidence_avg REAL,
                ai_suggested_category TEXT,
                ai_suggested_filename TEXT,
                ai_confidence REAL,
                ai_summary TEXT,
                final_category TEXT,
                final_filename TEXT,
                status TEXT NOT NULL DEFAULT 'processing',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                FOREIGN KEY (batch_id) REFERENCES batches(id)
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("CREATE INDEX idx_single_documents_batch_id ON single_documents(batch_id)")
        cursor.execute("CREATE INDEX idx_single_documents_status ON single_documents(status)")
        
        conn.commit()
        
        print("✓ Created single_documents table with indexes")
        print("✓ Database schema updated for improved single document workflow")
        
    except Exception as e:
        print(f"Error adding single_documents table: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    add_single_documents_table()
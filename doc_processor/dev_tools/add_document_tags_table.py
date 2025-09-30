#!/usr/bin/env python3
"""
Add document_tags table for tag-based RAG functionality.

This creates a new table to store structured tags extracted from documents:
- Enables tag-based document similarity search
- Supports RAG-enhanced classification and naming
- Provides foundation for intelligent pattern recognition
"""

import sqlite3
import logging
import sys
import os

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import get_db_connection

def add_document_tags_table():
    """
    Add the document_tags table to the database for RAG functionality.
    """
    logging.basicConfig(level=logging.INFO)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if table already exists
        result = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='document_tags'"
        ).fetchone()
        
        if result:
            print("document_tags table already exists. Skipping creation.")
            return
        
        # Create the document_tags table
        cursor.execute("""
            CREATE TABLE document_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                tag_category TEXT NOT NULL CHECK(tag_category IN (
                    'people', 'organizations', 'places', 'dates', 
                    'document_types', 'keywords', 'amounts', 'reference_numbers'
                )),
                tag_value TEXT NOT NULL,
                extraction_confidence REAL DEFAULT 1.0,
                llm_source TEXT DEFAULT 'ollama',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES single_documents(id) ON DELETE CASCADE,
                UNIQUE(document_id, tag_category, tag_value)
            )
        """)
        
        # Create indexes for efficient tag-based queries
        cursor.execute("CREATE INDEX idx_document_tags_category_value ON document_tags(tag_category, tag_value)")
        cursor.execute("CREATE INDEX idx_document_tags_document_id ON document_tags(document_id)")
        cursor.execute("CREATE INDEX idx_document_tags_category ON document_tags(tag_category)")
        cursor.execute("CREATE INDEX idx_document_tags_value ON document_tags(tag_value)")
        
        # Create view for tag analysis
        cursor.execute("""
            CREATE VIEW tag_usage_stats AS
            SELECT 
                tag_category,
                tag_value,
                COUNT(*) as usage_count,
                COUNT(DISTINCT document_id) as document_count,
                AVG(extraction_confidence) as avg_confidence,
                MIN(created_at) as first_used,
                MAX(created_at) as last_used
            FROM document_tags 
            GROUP BY tag_category, tag_value
            ORDER BY usage_count DESC
        """)
        
        conn.commit()
        
        print("✓ Created document_tags table with indexes")
        print("✓ Created tag_usage_stats view for analysis")
        print("✓ Database schema updated for tag-based RAG functionality")
        
        # Print schema summary
        print("\nNew table schema:")
        print("document_tags:")
        print("  - id: Primary key")
        print("  - document_id: Foreign key to single_documents")
        print("  - tag_category: One of 8 predefined categories")
        print("  - tag_value: The actual tag text")
        print("  - extraction_confidence: AI confidence score")
        print("  - llm_source: Which LLM extracted the tag")
        print("  - created_at: Timestamp")
        print("  - Unique constraint on (document_id, tag_category, tag_value)")
        
    except Exception as e:
        print(f"Error adding document_tags table: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    add_document_tags_table()
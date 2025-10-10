#!/usr/bin/env python3
"""
Database upgrade script to add single document support columns.
Adds file_type and processing_strategy columns to documents table with safe defaults.
"""

import os
import sys
import sqlite3
from pathlib import Path

# Add doc_processor to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import app_config

def upgrade_database():
    """Add columns for single document support with safe defaults."""
    print(f"Upgrading database at: {app_config.DATABASE_PATH}")
    
    # Prefer centralized DB helper to get consistent PRAGMA settings when run
    # within the application context. Fallback to direct connect for standalone runs.
    conn = None
    try:
        from ..database import get_db_connection
        conn = get_db_connection()
    except Exception:
        conn = sqlite3.connect(app_config.DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        # Add file_type column (defaults to 'pdf' for existing records)
        try:
            cursor.execute("ALTER TABLE documents ADD COLUMN file_type TEXT DEFAULT 'pdf'")
            print("✓ Added file_type column to documents table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("- file_type column already exists")
            else:
                raise
        
        # Add processing_strategy column (defaults to 'batch_scan' for existing records)
        try:
            cursor.execute("ALTER TABLE documents ADD COLUMN processing_strategy TEXT DEFAULT 'batch_scan'")
            print("✓ Added processing_strategy column to documents table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("- processing_strategy column already exists")
            else:
                raise
                
        # Add original_file_path column for tracking source files in single-doc workflow
        try:
            cursor.execute("ALTER TABLE documents ADD COLUMN original_file_path TEXT")
            print("✓ Added original_file_path column to documents table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("- original_file_path column already exists")
            else:
                raise
        
        conn.commit()
        print("✓ Database upgrade completed successfully")
        
    except Exception as e:
        print(f"✗ Error during database upgrade: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    upgrade_database()
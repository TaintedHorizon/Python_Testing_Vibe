#!/usr/bin/env python3
"""
Database upgrade script to add single document support columns.
Adds file_type and processing_strategy columns to documents table with safe defaults.
"""

import os
import sys
import sqlite3
from doc_processor.dev_tools.db_connect import connect as db_connect
from pathlib import Path

# Add doc_processor to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import app_config
import sqlite3
import os
import argparse
import sys

# CLI parsing for safety
parser = argparse.ArgumentParser(description='Add single-document support columns to documents table (destructive)')
parser.add_argument('--dry-run', action='store_true', help='Show changes without applying them')
parser.add_argument('--yes', '-y', action='store_true', help='Auto-confirm destructive actions (or set CONFIRM_RESET=1)')
args = parser.parse_args()

dry_run = args.dry_run or os.getenv('DRY_RUN','0').lower() in ('1','true','t')
env_confirm = os.getenv('CONFIRM_RESET','0').lower() in ('1','true','t')
if not (env_confirm or args.yes):
    confirm = input("This will MODIFY the documents table. Type 'yes' to continue: ")
    if confirm.lower() != 'yes':
        print("Operation cancelled (no confirmation).")
        sys.exit(0)

def _connect_preferring_helper(path):
    try:
        # Prefer the centralized dev_tools helper which will return the
        # application's get_db_connection() when the path matches the
        # configured DATABASE_PATH. This ensures PRAGMAs/WAL and safety
        # guards are applied consistently.
        conn = db_connect(path, timeout=30.0)
        return conn
    except Exception:
        # As a last-resort fallback, use sqlite3.connect directly. Keep the
        # explicit str() conversion for Path objects.
        return sqlite3.connect(str(path), timeout=30.0)

def upgrade_database():
    """Add columns for single document support with safe defaults."""
    print(f"Upgrading database at: {app_config.DATABASE_PATH}")
    
    # Prefer centralized DB helper to get consistent PRAGMA settings when run
    # within the application context. Fallback to direct connect for standalone runs.
    conn = None
    conn = _connect_preferring_helper(app_config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Add file_type column (defaults to 'pdf' for existing records)
        try:
            if dry_run:
                print("DRY-RUN: would add column 'file_type' to documents")
            else:
                cursor.execute("ALTER TABLE documents ADD COLUMN file_type TEXT DEFAULT 'pdf'")
                print("✓ Added file_type column to documents table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("- file_type column already exists")
            else:
                raise
        
        # Add processing_strategy column (defaults to 'batch_scan' for existing records)
        try:
            if dry_run:
                print("DRY-RUN: would add column 'processing_strategy' to documents")
            else:
                cursor.execute("ALTER TABLE documents ADD COLUMN processing_strategy TEXT DEFAULT 'batch_scan'")
                print("✓ Added processing_strategy column to documents table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("- processing_strategy column already exists")
            else:
                raise
                
        # Add original_file_path column for tracking source files in single-doc workflow
        try:
            if dry_run:
                print("DRY-RUN: would add column 'original_file_path' to documents")
            else:
                cursor.execute("ALTER TABLE documents ADD COLUMN original_file_path TEXT")
                print("✓ Added original_file_path column to documents table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("- original_file_path column already exists")
            else:
                raise

        if dry_run:
            print("DRY-RUN: no changes were committed.")
        else:
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
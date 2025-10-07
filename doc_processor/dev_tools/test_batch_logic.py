#!/usr/bin/env python3
"""Diagnostic / legacy script (not part of automated pytest suite).

Marked skipped under pytest to avoid import mismatch with refactored app.
"""
import pytest  # type: ignore
pytest.skip("Legacy dev_tools diagnostic script - skipping in automated test run", allow_module_level=True)
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from doc_processor.app import get_db_connection
import sqlite3

def test_batch_logic():
    print("🔍 Testing Batch Control Logic")
    print("=" * 40)
    
    # Test database connection and data
    conn = get_db_connection()
    batch_raw = conn.execute("SELECT * FROM batches WHERE id = 4").fetchone()
    conn.close()
    
    if not batch_raw:
        print("❌ Batch 4 not found")
        return
        
    batch_dict = dict(batch_raw)
    print(f"📊 Batch 4 Data: {batch_dict}")
    
    # Test the template logic
    if batch_dict['status'] == 'ready_for_manipulation':
        print(f"✅ Status is 'ready_for_manipulation'")
        
        if batch_dict['has_been_manipulated']:
            print(f"🎯 has_been_manipulated = {batch_dict['has_been_manipulated']} (truthy)")
            print("   → Should show: 'Export Single Documents'")
        else:
            print(f"🛠️ has_been_manipulated = {batch_dict['has_been_manipulated']} (falsy)")
            print("   → Should show: 'Manipulate Single Documents'")
    else:
        print(f"❌ Status is '{batch_dict['status']}' (not ready_for_manipulation)")

if __name__ == "__main__":
    test_batch_logic()
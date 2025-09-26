#!/usr/bin/env python3
"""
Test database path consistency from different working directories.
This ensures the duplicate doc_processor/doc_processor/ directory doesn't reappear.
"""

import os
import sys
import tempfile

# Test from different working directories
test_directories = [
    "/home/svc-scan/Python_Testing_Vibe",
    "/home/svc-scan/Python_Testing_Vibe/doc_processor", 
    "/tmp"
]

def test_database_path():
    """Test database path resolution from different working directories."""
    
    original_cwd = os.getcwd()
    results = []
    
    for test_dir in test_directories:
        try:
            # Change to test directory
            os.chdir(test_dir)
            
            # Add doc_processor to path
            sys.path.insert(0, "/home/svc-scan/Python_Testing_Vibe/doc_processor")
            
            # Import and get database path
            from config_manager import app_config
            
            db_path = app_config.DATABASE_PATH
            results.append((test_dir, db_path))
            
            print(f"Working Dir: {test_dir}")
            print(f"Database Path: {db_path}")
            print(f"Absolute Path: {os.path.abspath(db_path)}")
            print()
            
        except Exception as e:
            print(f"Error from {test_dir}: {e}")
            results.append((test_dir, f"ERROR: {e}"))
        finally:
            os.chdir(original_cwd)
    
    # Check if all paths resolve to the same absolute location
    absolute_paths = []
    for test_dir, db_path in results:
        if not db_path.startswith("ERROR:"):
            # Temporarily change to test dir to resolve relative paths correctly
            os.chdir(test_dir)
            abs_path = os.path.abspath(db_path)
            absolute_paths.append(abs_path)
            os.chdir(original_cwd)
    
    if len(set(absolute_paths)) == 1:
        print("✅ SUCCESS: All database paths resolve to the same location!")
        print(f"   Consistent path: {absolute_paths[0]}")
        
        # Check if the problematic duplicate path would be created
        duplicate_path = "/home/svc-scan/Python_Testing_Vibe/doc_processor/doc_processor/documents.db"
        if absolute_paths[0] != duplicate_path:
            print("✅ SUCCESS: No duplicate doc_processor/doc_processor/ path!")
        else:
            print("❌ WARNING: Duplicate path still being created!")
            
    else:
        print("❌ FAILURE: Database paths are inconsistent!")
        for i, path in enumerate(absolute_paths):
            print(f"   Path {i+1}: {path}")

if __name__ == "__main__":
    print("🔍 Testing Database Path Consistency...")
    print("=" * 60)
    
    test_database_path()
    
    print("\n" + "=" * 60)
    print("💡 This test ensures the duplicate doc_processor/doc_processor/documents.db")
    print("   directory doesn't reappear during testing or normal operation.")
#!/usr/bin/env python3
import os
import sys

# Ensure project root is on sys.path so package imports resolve
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

def main():
    try:
        from doc_processor.dev_tools import database_setup
        database_setup.create_database()
        print("Database setup/migration finished.")
    except Exception as e:
        print(f"Database setup failed: {e}")
        raise

if __name__ == '__main__':
    main()

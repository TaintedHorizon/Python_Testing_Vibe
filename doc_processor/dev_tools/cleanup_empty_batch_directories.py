#!/usr/bin/env python3
"""
Manual cleanup utility for empty batch directories.

This tool scans the processed directory for empty batch folders and removes them.
Useful for cleaning up after incomplete processing or manual maintenance.
"""

import os
import sys
import logging

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import argparse
import sys
from config_manager import app_config
from processing import cleanup_empty_batch_directory

parser = argparse.ArgumentParser(description='Cleanup empty batch directories (destructive)')
parser.add_argument('--batch', type=int, help='Specific batch ID to cleanup (optional)')
parser.add_argument('--dry-run', action='store_true', help='Show what would be done without applying changes')
parser.add_argument('--yes', '-y', action='store_true', help='Auto-confirm destructive actions (or set CONFIRM_RESET=1)')
args = parser.parse_args()

dry_run = args.dry_run or os.getenv('DRY_RUN','0').lower() in ('1','true','t')
env_confirm = os.getenv('CONFIRM_RESET','0').lower() in ('1','true','t')
if args.batch and not (env_confirm or args.yes):
    confirm = input(f"This will delete files for batch {args.batch} if empty. Type 'yes' to continue: ")
    if confirm.lower() != 'yes':
        print("Operation cancelled (no confirmation).")
        sys.exit(0)

def scan_and_cleanup_empty_directories():
    """
    Scan the processed directory for empty batch directories and clean them up.
    """
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    processed_dir = app_config.PROCESSED_DIR
    if not os.path.exists(processed_dir):
        print(f"Processed directory does not exist: {processed_dir}")
        return

    print(f"Scanning for empty batch directories in: {processed_dir}")
    print()

    # Find all numeric directory names (batch IDs)
    batch_dirs = []
    for item in os.listdir(processed_dir):
        item_path = os.path.join(processed_dir, item)
        if os.path.isdir(item_path) and item.isdigit():
            batch_dirs.append((int(item), item_path))

    batch_dirs.sort()  # Sort by batch ID

    if not batch_dirs:
        print("No batch directories found.")
        return

    print(f"Found {len(batch_dirs)} batch directories:")

    cleaned_count = 0
    kept_count = 0

    for batch_id, batch_path in batch_dirs:
        print(f"\nBatch {batch_id}: {batch_path}")

        # Check if directory is empty recursively
        def count_files_recursive(path):
            count = 0
            for root, dirs, files in os.walk(path):
                count += len(files)
            return count

        file_count = count_files_recursive(batch_path)

        if file_count == 0:
            print("  📁 Empty directory - attempting cleanup...")
            success = cleanup_empty_batch_directory(batch_id)
            if success:
                print("  ✅ Cleaned up successfully")
                cleaned_count += 1
            else:
                print("  ❌ Cleanup failed")
                kept_count += 1
        else:
            print(f"  📄 Contains {file_count} files - keeping")
            kept_count += 1

    print("\n=== CLEANUP SUMMARY ===")
    print(f"✅ Cleaned up: {cleaned_count} directories")
    print(f"📁 Kept: {kept_count} directories")
    print(f"📊 Total scanned: {len(batch_dirs)} directories")

def cleanup_specific_batch(batch_id: int):
    """
    Clean up a specific batch directory by ID.

    Args:
        batch_id (int): The batch ID to clean up
    """
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    print(f"Attempting to clean up batch {batch_id}...")
    success = cleanup_empty_batch_directory(batch_id)

    if success:
        print(f"✅ Batch {batch_id} cleanup completed successfully")
    else:
        print(f"❌ Batch {batch_id} cleanup failed or directory not empty")

if __name__ == "__main__":
    if args.batch:
        cleanup_specific_batch(args.batch)
    else:
        if dry_run:
            print("DRY-RUN mode - no directories will be removed. Showing what would be done:")
        scan_and_cleanup_empty_directories()
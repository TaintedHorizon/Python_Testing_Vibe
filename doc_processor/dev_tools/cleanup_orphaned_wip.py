#!/usr/bin/env python3
"""
Cleanup script to remove orphaned WIP batch directories.
These directories contain files from batches that were consolidated into batch 1.
"""

import os
import sys
import shutil
import subprocess
from datetime import datetime

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import sys
from config_manager import app_config
import tempfile

# Backup base for destructive cleanup operations. Use env var or system tempdir by default.
WIP_CLEANUP_BACKUP_BASE = os.environ.get('WIP_CLEANUP_BACKUP_BASE') or os.environ.get('DEV_TOOL_BACKUP_DIR') or tempfile.gettempdir()

parser = argparse.ArgumentParser(description='Cleanup orphaned WIP batch directories (destructive)')
parser.add_argument('--dry-run', action='store_true', help='Show what would be done without applying changes')
parser.add_argument('--yes', '-y', action='store_true', help='Auto-confirm destructive actions (or set CONFIRM_RESET=1)')
args = parser.parse_args()

dry_run = args.dry_run or os.getenv('DRY_RUN','0').lower() in ('1','true','t')
env_confirm = os.getenv('CONFIRM_RESET','0').lower() in ('1','true','t')
if not (env_confirm or args.yes):
    confirm = input("This will permanently delete WIP batch directories after backing up. Type 'yes' to continue: ")
    if confirm.lower() != 'yes':
        print("Operation cancelled (no confirmation).")
        sys.exit(0)

def cleanup_orphaned_wip_batches():
    """Remove WIP directories for batches that no longer exist in database."""

    # Use config manager for paths
    wip_base = app_config.PROCESSED_DIR
    # place backups in configured base (outside repo by default) to avoid writing into repo
    backup_dir = os.path.join(WIP_CLEANUP_BACKUP_BASE, f"wip_cleanup_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    # These are the orphaned batch directories we identified
    orphaned_batches = [4, 5, 6, 8, 9]

    print("=== WIP CLEANUP - ORPHANED BATCH DIRECTORIES ===\\n")

    # Create backup directory first
    print(f"Creating backup directory: {backup_dir}")
    os.makedirs(backup_dir, exist_ok=True)

    total_files_removed = 0

    for batch_id in orphaned_batches:
        batch_wip_dir = os.path.join(wip_base, str(batch_id))

        if os.path.exists(batch_wip_dir):
            print(f"\n--- Processing Batch {batch_id} ---")

            # Count files before cleanup
            try:
                result = subprocess.run(['find', batch_wip_dir, '-type', 'f'],
                                      capture_output=True, text=True, check=True)
                files = result.stdout.strip().split('\n')
                file_count = len([f for f in files if f.strip()])

                print(f"Found {file_count} files in {batch_wip_dir}")

                if file_count > 0:
                    # Move to backup before deletion
                    backup_batch_dir = os.path.join(backup_dir, f"batch_{batch_id}")
                    print(f"Backing up to: {backup_batch_dir}")
                    if not dry_run:
                        shutil.copytree(batch_wip_dir, backup_batch_dir)
                        # Remove the original
                        print(f"Removing: {batch_wip_dir}")
                        shutil.rmtree(batch_wip_dir)
                    else:
                        print("DRY-RUN: would copy and remove the directory")

                    total_files_removed += file_count
                    print(f"✅ Removed batch {batch_id} WIP directory ({file_count} files)")
                else:
                    print(f"📁 Empty directory, removing: {batch_wip_dir}")
                    if not dry_run:
                        shutil.rmtree(batch_wip_dir)
                    else:
                        print("DRY-RUN: would remove empty directory")

            except subprocess.CalledProcessError as e:
                print(f"❌ Error processing batch {batch_id}: {e}")
            except Exception as e:
                print(f"❌ Unexpected error with batch {batch_id}: {e}")
        else:
            print(f"⚠️ Batch {batch_id} WIP directory does not exist")

    print("\n=== CLEANUP SUMMARY ===")
    print(f"✅ Total files backed up and removed: {total_files_removed}")
    print(f"📦 Backup location: {backup_dir}")
    print("🧹 Orphaned WIP directories cleaned up")

    # Show remaining WIP directories
    try:
        remaining_dirs = [d for d in os.listdir(wip_base)
                         if os.path.isdir(os.path.join(wip_base, d)) and d.isdigit()]
        if remaining_dirs:
            print(f"\n📂 Remaining WIP directories: {remaining_dirs}")
        else:
            print("\n🎉 All WIP directories cleaned up!")
    except Exception as e:
        print(f"⚠️ Could not list remaining directories: {e}")

if __name__ == "__main__":
    cleanup_orphaned_wip_batches()
#!/usr/bin/env python3
"""
Filing Cabinet Naming Cleanup Tool

This utility scans the filing cabinet directory and standardizes all directory
and file names to match the new consistent naming convention:
- Directory names: spaces → underscores, alphanumeric + hyphens/underscores only
- Filenames: non-alphanumeric → underscores (except dots/hyphens)

Features:
- Preview mode (dry-run) to see changes before applying
- Backup creation before any modifications
- Rollback capability if issues occur
- Conflict resolution for duplicate names
- Detailed logging of all operations
"""

import os
import sys
import shutil
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional

# Add parent directory to path to import doc_processor modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from doc_processor.config_manager import app_config
    from doc_processor.processing import _sanitize_category
    from doc_processor.security import sanitize_filename
except ImportError as e:
    print(f"Error importing doc_processor modules: {e}")
    print("Make sure you're running this from the project root directory with the virtual environment activated")
    sys.exit(1)

class FilingCabinetCleanup:
    """Utility class for cleaning up filing cabinet naming conventions."""

    def __init__(self, filing_cabinet_path: Optional[str] = None):
        self.filing_cabinet_path = filing_cabinet_path or app_config.FILING_CABINET_DIR
        if not self.filing_cabinet_path:
            raise ValueError("FILING_CABINET_DIR not configured in .env file")

        self.backup_dir = os.path.join(self.filing_cabinet_path, ".cleanup_backup")
        self.log_file = os.path.join(self.filing_cabinet_path, "cleanup_log.json")

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(self.filing_cabinet_path, "cleanup.log")),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

        # Track changes for rollback
        self.changes_log = []

    def scan_filing_cabinet(self) -> Dict:
        """
        Scan the filing cabinet and identify all directories and files that need renaming.

        Returns:
            Dict with scan results including directories and files to rename
        """
        if not os.path.exists(self.filing_cabinet_path):
            raise FileNotFoundError(f"Filing cabinet directory not found: {self.filing_cabinet_path}")

        scan_results = {
            "directories_to_rename": [],
            "files_to_rename": [],
            "total_directories": 0,
            "total_files": 0,
            "scan_timestamp": datetime.now().isoformat()
        }

        self.logger.info(f"Scanning filing cabinet: {self.filing_cabinet_path}")

        # Scan all directories and files
        for root, dirs, files in os.walk(self.filing_cabinet_path):
            # Skip backup directory
            if ".cleanup_backup" in root:
                continue

            # Check directory names
            for dir_name in dirs:
                if dir_name.startswith('.'):  # Skip hidden directories
                    continue

                scan_results["total_directories"] += 1
                sanitized_name = _sanitize_category(dir_name)

                if dir_name != sanitized_name:
                    dir_path = os.path.join(root, dir_name)
                    new_path = os.path.join(root, sanitized_name)

                    scan_results["directories_to_rename"].append({
                        "original_path": dir_path,
                        "new_path": new_path,
                        "original_name": dir_name,
                        "new_name": sanitized_name,
                        "relative_path": os.path.relpath(dir_path, self.filing_cabinet_path)
                    })

            # Check file names
            for file_name in files:
                if file_name.startswith('.') or file_name in ['cleanup.log', 'cleanup_log.json']:
                    continue

                scan_results["total_files"] += 1
                sanitized_name = sanitize_filename(file_name)

                if file_name != sanitized_name:
                    file_path = os.path.join(root, file_name)
                    new_path = os.path.join(root, sanitized_name)

                    scan_results["files_to_rename"].append({
                        "original_path": file_path,
                        "new_path": new_path,
                        "original_name": file_name,
                        "new_name": sanitized_name,
                        "relative_path": os.path.relpath(file_path, self.filing_cabinet_path)
                    })

        return scan_results

    def check_for_conflicts(self, scan_results: Dict) -> List[Dict]:
        """
        Check for potential naming conflicts after sanitization.

        Args:
            scan_results: Results from scan_filing_cabinet()

        Returns:
            List of conflicts that need resolution
        """
        conflicts = []

        # Check directory conflicts
        new_dir_names = {}
        for item in scan_results["directories_to_rename"]:
            new_name = item["new_name"]
            parent_dir = os.path.dirname(item["original_path"])

            key = f"{parent_dir}/{new_name}"
            if key in new_dir_names:
                conflicts.append({
                    "type": "directory",
                    "conflict_name": new_name,
                    "conflicting_paths": [new_dir_names[key], item["original_path"]],
                    "parent_dir": parent_dir
                })
            else:
                new_dir_names[key] = item["original_path"]

        # Check file conflicts
        new_file_names = {}
        for item in scan_results["files_to_rename"]:
            new_name = item["new_name"]
            parent_dir = os.path.dirname(item["original_path"])

            key = f"{parent_dir}/{new_name}"
            if key in new_file_names:
                conflicts.append({
                    "type": "file",
                    "conflict_name": new_name,
                    "conflicting_paths": [new_file_names[key], item["original_path"]],
                    "parent_dir": parent_dir
                })
            else:
                new_file_names[key] = item["original_path"]

        return conflicts

    def resolve_conflicts(self, conflicts: List[Dict]) -> Dict:
        """
        Resolve naming conflicts by adding numeric suffixes.

        Args:
            conflicts: List of conflicts from check_for_conflicts()

        Returns:
            Dict mapping original paths to conflict-resolved names
        """
        resolutions = {}

        for conflict in conflicts:
            self.logger.warning(f"Resolving {conflict['type']} naming conflict: {conflict['conflict_name']}")

            for i, path in enumerate(conflict["conflicting_paths"]):
                if i == 0:
                    # First file keeps original sanitized name
                    continue
                else:
                    # Add numeric suffix to subsequent files
                    name = conflict["conflict_name"]
                    if "." in name:
                        base, ext = name.rsplit(".", 1)
                        resolved_name = f"{base}_{i}.{ext}"
                    else:
                        resolved_name = f"{name}_{i}"

                    resolutions[path] = resolved_name
                    self.logger.info(f"  {os.path.basename(path)} → {resolved_name}")

        return resolutions

    def create_backup(self) -> bool:
        """
        Create a backup of the current filing cabinet state.

        Returns:
            bool: True if backup successful, False otherwise
        """
        try:
            if os.path.exists(self.backup_dir):
                shutil.rmtree(self.backup_dir)

            self.logger.info(f"Creating backup at: {self.backup_dir}")
            shutil.copytree(self.filing_cabinet_path, self.backup_dir,
                          ignore=shutil.ignore_patterns('.cleanup_backup', 'cleanup.log', 'cleanup_log.json'))

            self.logger.info("✓ Backup created successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return False

    def apply_rename_operations(self, scan_results: Dict, conflict_resolutions: Optional[Dict] = None, dry_run: bool = True) -> bool:
        """
        Apply the rename operations to clean up the filing cabinet.

        Args:
            scan_results: Results from scan_filing_cabinet()
            conflict_resolutions: Optional conflict resolutions from resolve_conflicts()
            dry_run: If True, only show what would be done without making changes

        Returns:
            bool: True if successful, False otherwise
        """
        if conflict_resolutions is None:
            conflict_resolutions = {}

        if dry_run:
            self.logger.info("=== DRY RUN MODE - NO CHANGES WILL BE MADE ===")
        else:
            self.logger.info("=== APPLYING RENAME OPERATIONS ===")

        success = True
        operations_count = 0

        try:
            # Process files first, then directories (to avoid path changes affecting file operations)
            for item in scan_results["files_to_rename"]:
                original_path = item["original_path"]
                new_name = conflict_resolutions.get(original_path, item["new_name"])
                new_path = os.path.join(os.path.dirname(original_path), new_name)

                self.logger.info(f"File: {item['relative_path']} → {new_name}")

                if not dry_run:
                    # Check if the original file still exists (might have been moved during directory merge)
                    if not os.path.exists(original_path):
                        self.logger.warning(f"File no longer exists (possibly moved during directory merge): {original_path}")
                        continue

                    if os.path.exists(new_path):
                        # Target file already exists - add timestamp suffix
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        name, ext = os.path.splitext(new_name)
                        conflict_name = f"{name}_{timestamp}{ext}"
                        new_path = os.path.join(os.path.dirname(original_path), conflict_name)
                        self.logger.info(f"  Target exists, using conflict name: {conflict_name}")

                    os.rename(original_path, new_path)
                    self.changes_log.append({
                        "type": "file",
                        "original": original_path,
                        "new": new_path,
                        "timestamp": datetime.now().isoformat()
                    })

                operations_count += 1

            # Process directories (from deepest to shallowest to avoid path issues)
            directories = sorted(scan_results["directories_to_rename"],
                               key=lambda x: x["original_path"].count(os.sep), reverse=True)

            for item in directories:
                original_path = item["original_path"]
                new_name = conflict_resolutions.get(original_path, item["new_name"])
                new_path = os.path.join(os.path.dirname(original_path), new_name)

                self.logger.info(f"Directory: {item['relative_path']} → {new_name}")

                if not dry_run:
                    if os.path.exists(new_path):
                        # Target directory already exists - merge contents instead of rename
                        self.logger.info(f"  Target exists, merging contents from {item['original_name']} into {new_name}")

                        # Move all contents from old directory to new directory
                        for content_item in os.listdir(original_path):
                            src_item = os.path.join(original_path, content_item)
                            dst_item = os.path.join(new_path, content_item)

                            # Handle conflicts in the content
                            if os.path.exists(dst_item):
                                # Add timestamp suffix to avoid conflicts
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                if os.path.isfile(src_item):
                                    name, ext = os.path.splitext(content_item)
                                    dst_item = os.path.join(new_path, f"{name}_{timestamp}{ext}")
                                else:
                                    dst_item = os.path.join(new_path, f"{content_item}_{timestamp}")
                                self.logger.info(f"    Conflict resolved: {content_item} → {os.path.basename(dst_item)}")

                            shutil.move(src_item, dst_item)

                        # Remove the empty old directory
                        os.rmdir(original_path)

                        self.changes_log.append({
                            "type": "directory_merge",
                            "original": original_path,
                            "target": new_path,
                            "timestamp": datetime.now().isoformat()
                        })
                    else:
                        # Simple rename
                        os.rename(original_path, new_path)
                        self.changes_log.append({
                            "type": "directory",
                            "original": original_path,
                            "new": new_path,
                            "timestamp": datetime.now().isoformat()
                        })

                operations_count += 1

        except Exception as e:
            self.logger.error(f"Error during rename operations: {e}")
            success = False

        if dry_run:
            self.logger.info(f"=== DRY RUN COMPLETE - {operations_count} operations would be performed ===")
        else:
            self.logger.info(f"=== RENAME OPERATIONS COMPLETE - {operations_count} operations performed ===")

            # Save changes log
            if self.changes_log:
                with open(self.log_file, 'w') as f:
                    json.dump(self.changes_log, f, indent=2)

        return success

    def rollback_changes(self) -> bool:
        """
        Rollback all changes using the backup.

        Returns:
            bool: True if rollback successful, False otherwise
        """
        if not os.path.exists(self.backup_dir):
            self.logger.error("No backup found for rollback")
            return False

        try:
            self.logger.info("Rolling back changes...")

            # Remove current filing cabinet (except backup)
            for item in os.listdir(self.filing_cabinet_path):
                if item == ".cleanup_backup":
                    continue
                item_path = os.path.join(self.filing_cabinet_path, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

            # Restore from backup
            for item in os.listdir(self.backup_dir):
                src = os.path.join(self.backup_dir, item)
                dst = os.path.join(self.filing_cabinet_path, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            self.logger.info("✓ Rollback completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            return False

def main():
    """Main function to run the filing cabinet cleanup utility."""
    import argparse

    parser = argparse.ArgumentParser(description="Filing Cabinet Naming Cleanup Tool")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying them")
    parser.add_argument("--apply", action="store_true", help="Apply the cleanup changes")
    parser.add_argument("--rollback", action="store_true", help="Rollback previous changes")
    parser.add_argument("--filing-cabinet", help="Override filing cabinet directory path")

    args = parser.parse_args()

    if not any([args.dry_run, args.apply, args.rollback]):
        parser.print_help()
        print("\nMust specify one of: --dry-run, --apply, or --rollback")
        sys.exit(1)

    try:
        cleanup = FilingCabinetCleanup(args.filing_cabinet)

        if args.rollback:
            success = cleanup.rollback_changes()
            sys.exit(0 if success else 1)

        # Scan the filing cabinet
        print("Scanning filing cabinet...")
        scan_results = cleanup.scan_filing_cabinet()

        directories_to_rename = len(scan_results["directories_to_rename"])
        files_to_rename = len(scan_results["files_to_rename"])

        print("\nScan Results:")
        print(f"  Total directories: {scan_results['total_directories']}")
        print(f"  Total files: {scan_results['total_files']}")
        print(f"  Directories needing rename: {directories_to_rename}")
        print(f"  Files needing rename: {files_to_rename}")

        if directories_to_rename == 0 and files_to_rename == 0:
            print("\n✓ All naming conventions are already standardized!")
            sys.exit(0)

        # Check for conflicts
        conflicts = cleanup.check_for_conflicts(scan_results)
        conflict_resolutions = {}

        if conflicts:
            print(f"\nFound {len(conflicts)} naming conflicts that need resolution:")
            for conflict in conflicts:
                print(f"  {conflict['type']}: {conflict['conflict_name']}")

            conflict_resolutions = cleanup.resolve_conflicts(conflicts)

        if args.dry_run:
            # Preview mode
            cleanup.apply_rename_operations(scan_results, conflict_resolutions, dry_run=True)

        elif args.apply:
            # Create backup first
            if not cleanup.create_backup():
                print("Failed to create backup. Aborting cleanup.")
                sys.exit(1)

            # Apply changes
            success = cleanup.apply_rename_operations(scan_results, conflict_resolutions, dry_run=False)

            if success:
                print("\n✓ Cleanup completed successfully!")
                print(f"  {directories_to_rename} directories renamed")
                print(f"  {files_to_rename} files renamed")
                print(f"\nBackup created at: {cleanup.backup_dir}")
                print("Use --rollback to undo changes if needed")
            else:
                print("\n❌ Cleanup completed with errors. Check logs for details.")
                print("Use --rollback to undo changes if needed")
                sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
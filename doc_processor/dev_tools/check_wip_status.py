#!/usr/bin/env python3
"""
Script to check if PDFs in WIP directories have been processed and moved to final locations.
Uses MD5 hashing to match files even if they've been renamed.
"""

import os
import sys
import hashlib
import subprocess
from collections import defaultdict

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_manager import app_config

def get_md5_hash(filepath):
    """Calculate MD5 hash of a file."""
    try:
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"Error hashing {filepath}: {e}")
        return None

def find_pdfs_and_hash(directory):
    """Find all PDFs in directory and return dict of {hash: filepath}."""
    pdf_hashes = {}
    
    try:
        # Use find command to get all PDFs
        result = subprocess.run(
            ['find', directory, '-name', '*.pdf', '-type', 'f'],
            capture_output=True, text=True, check=True
        )
        
        pdf_files = result.stdout.strip().split('\n')
        if pdf_files == ['']:  # No files found
            pdf_files = []
            
        print(f"Found {len(pdf_files)} PDF files in {directory}")
        
        for i, filepath in enumerate(pdf_files, 1):
            if filepath:  # Skip empty lines
                print(f"  Hashing {i}/{len(pdf_files)}: {os.path.basename(filepath)}")
                file_hash = get_md5_hash(filepath)
                if file_hash:
                    pdf_hashes[file_hash] = filepath
                    
    except subprocess.CalledProcessError as e:
        print(f"Error finding PDFs in {directory}: {e}")
    except Exception as e:
        print(f"Unexpected error processing {directory}: {e}")
        
    return pdf_hashes

def main():
    # Use config manager for paths
    wip_dir = app_config.PROCESSED_DIR
    final_dir = app_config.FILING_CABINET_DIR
    
    print("=== PDF Processing Status Check ===\n")
    
    # Get hashes for all PDFs in both directories
    print("1. Analyzing WIP directory...")
    wip_hashes = find_pdfs_and_hash(wip_dir)
    
    print(f"\n2. Analyzing FINAL directory...")
    final_hashes = find_pdfs_and_hash(final_dir)
    
    print(f"\n=== RESULTS ===")
    print(f"WIP PDFs: {len(wip_hashes)}")
    print(f"Final PDFs: {len(final_hashes)}")
    
    # Check which WIP files have been processed
    processed_count = 0
    unprocessed_count = 0
    
    print(f"\n=== WIP FILE STATUS ===")
    
    for wip_hash, wip_path in wip_hashes.items():
        wip_filename = os.path.basename(wip_path)
        wip_batch = wip_path.split('/wip/')[1].split('/')[0] if '/wip/' in wip_path else 'unknown'
        
        if wip_hash in final_hashes:
            processed_count += 1
            final_path = final_hashes[wip_hash]
            final_filename = os.path.basename(final_path)
            final_category = os.path.dirname(final_path).split('/')[-1]
            print(f"✅ PROCESSED - Batch {wip_batch}: {wip_filename}")
            print(f"   └─ Found in: {final_category}/{final_filename}")
        else:
            unprocessed_count += 1
            print(f"❌ UNPROCESSED - Batch {wip_batch}: {wip_filename}")
            print(f"   └─ Location: {wip_path}")
    
    print(f"\n=== SUMMARY ===")
    print(f"✅ Processed files: {processed_count}")
    print(f"❌ Unprocessed files: {unprocessed_count}")
    
    if unprocessed_count > 0:
        print(f"\n=== UNPROCESSED FILES BY BATCH ===")
        unprocessed_by_batch = defaultdict(list)
        
        for wip_hash, wip_path in wip_hashes.items():
            if wip_hash not in final_hashes:
                wip_batch = wip_path.split('/wip/')[1].split('/')[0] if '/wip/' in wip_path else 'unknown'
                unprocessed_by_batch[wip_batch].append(os.path.basename(wip_path))
        
        for batch, files in sorted(unprocessed_by_batch.items()):
            print(f"\nBatch {batch}: {len(files)} unprocessed files")
            for filename in files:
                print(f"  - {filename}")

if __name__ == "__main__":
    main()
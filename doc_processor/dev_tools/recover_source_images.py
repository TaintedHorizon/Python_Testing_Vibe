"""Recover original source images for an already-exported batch.

Usage:
    Activate venv then run:
        python dev_tools/recover_source_images.py --batch 7

This script copies archived intake images from ARCHIVE_DIR/batch_<id>_images into
corresponding filing cabinet category folders alongside exported PDFs.

Matching Strategy:
 1. For each single_document in the batch, take the stem of original_pdf_path.
 2. Look for an archived image whose stem (case-insensitive, ignoring non-alnum) matches.
 3. If found and a *_source<ext> file does not already exist in the category folder, copy it.

Safe Re-Run: The script is idempotent; existing destination files are skipped.
"""
from __future__ import annotations
import argparse
import os
import logging
import shutil
import sqlite3

from config_manager import app_config

SUPPORTED_IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.gif', '.webp', '.heic']

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def simplify(s: str) -> str:
    return ''.join(c for c in s.lower() if c.isalnum())

def recover(batch_id: int, dry_run: bool = False) -> int:
    archive_dir = os.path.join(app_config.ARCHIVE_DIR, f"batch_{batch_id}_images")
    if not os.path.isdir(archive_dir):
        logging.error(f"Archive image directory not found: {archive_dir}")
        return 0

    # Build archive index
    archive_files = [f for f in os.listdir(archive_dir) if any(f.lower().endswith(ext) for ext in SUPPORTED_IMAGE_EXTS)]
    index = {}
    for f in archive_files:
        stem = os.path.splitext(f)[0]
        index.setdefault(simplify(stem), []).append(f)

    db_path = app_config.DATABASE_PATH
    if not os.path.exists(db_path):
        logging.error(f"Database not found at {db_path}")
        return 0

    try:
        from doc_processor.database import get_db_connection
        conn = get_db_connection()
    except Exception:
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, original_pdf_path, final_category, final_filename, ai_suggested_category, ai_suggested_filename FROM single_documents WHERE batch_id=?", (batch_id,))
    rows = cur.fetchall()
    if not rows:
        logging.warning(f"No single_documents found for batch {batch_id}")
        return 0

    copied = 0
    for (doc_id, original_pdf, final_cat, final_name, ai_cat, ai_name) in rows:
        stem = None
        if original_pdf:
            stem = os.path.splitext(os.path.basename(original_pdf))[0]
        candidate_stems = [s for s in {stem, final_name, ai_name} if s]
        # Category directory decision
        category = final_cat or ai_cat or 'Uncategorized'
        safe_category = ''.join(c for c in category if c.isalnum() or c in ('_', '-',' ')).rstrip().replace(' ', '_') or 'Other'
        category_dir = os.path.join(app_config.FILING_CABINET_DIR, safe_category)
        if not os.path.isdir(category_dir):
            logging.debug(f"Skipping doc {doc_id}: category folder missing {category_dir}")
            continue

        restored = False
        for cand in candidate_stems:
            if restored or not cand:
                continue
            key = simplify(cand)
            if key not in index:
                continue
            for fname in index[key]:
                ext = os.path.splitext(fname)[1].lower()
                src = os.path.join(archive_dir, fname)
                dest = os.path.join(category_dir, f"{(final_name or cand)}_source{ext}")
                if os.path.exists(dest):
                    logging.info(f"Skip (exists): {dest}")
                    restored = True
                    break
                if dry_run:
                    logging.info(f"DRY RUN would copy {src} -> {dest}")
                    restored = True
                    copied += 1
                    break
                try:
                    shutil.copy2(src, dest)
                    logging.info(f"Copied source image for doc {doc_id}: {src} -> {dest}")
                    restored = True
                    copied += 1
                    break
                except Exception as e:
                    logging.warning(f"Failed to copy {src} -> {dest}: {e}")
            # Stop after first successful restoration
        if not restored:
            logging.debug(f"No archived image found for doc {doc_id} (stems tried: {candidate_stems})")

    conn.close()
    return copied


def main():
    parser = argparse.ArgumentParser(description="Recover archived source images into exported filing cabinet structure")
    parser.add_argument('--batch', type=int, required=True, help='Batch ID to recover')
    parser.add_argument('--dry-run', action='store_true', help='Show actions without copying')
    args = parser.parse_args()

    total = recover(args.batch, dry_run=args.dry_run)
    logging.info(f"Done. Restored {total} images{' (dry run)' if args.dry_run else ''}.")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
recover_batch_tags.py

Recover / (re)generate tags and enriched markdown for an already-exported single-doc batch.

Use Cases:
- A batch was exported with ENABLE_TAG_EXTRACTION disabled / FAST_TEST_MODE enabled.
- You enabled tagging later and want markdown + DB tag records retroactively.

Strategy:
1. For each single_documents row in the batch:
   - Ensure ocr_text present; if missing and original_pdf_path exists, optionally attempt lightweight OCR (skipped if FAST_TEST_MODE is True).
   - Call extract_document_tags if tags not already stored.
   - Rebuild markdown using processing._create_single_document_markdown_content and overwrite the existing markdown file in the category directory.
2. Does NOT move/copy PDFs again; only touches metadata + markdown.

WARNING: This script assumes the batch has already been fully exported and its files reside under FILING_CABINET_DIR/<Category>.

Usage:
  python dev_tools/recover_batch_tags.py --batch 7 [--force-regen] [--skip-ocr]

Options:
  --batch / -b <id>       Batch ID to recover.
  --force-regen           Re-run tag extraction even if tags already exist in DB.
  --skip-ocr              Do not attempt OCR even if ocr_text is empty (will skip tag extraction if no text).
  --dry-run               Show what would be done without making changes.

Exit Codes:
  0 success, 1 error, 2 partial (some docs failed)
"""
import os
import sys
import sqlite3
import argparse
import logging
from typing import Optional

# Ensure local imports work when script run directly
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config_manager import app_config  # type: ignore
from llm_utils import extract_document_tags  # type: ignore

# Support both invocation styles:
# 1. python dev_tools/recover_batch_tags.py (with PROJECT_ROOT on sys.path)
# 2. python -m doc_processor.dev_tools.recover_batch_tags
try:
    from processing import _create_single_document_markdown_content  # type: ignore
except ImportError:
    try:
        from doc_processor.processing import _create_single_document_markdown_content  # type: ignore
    except Exception as _imp_err:
        raise ImportError(f"Failed to import _create_single_document_markdown_content: {_imp_err}")

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

TAG_TABLE = "document_tags"  # assumed existing via store_document_tags

# Lightweight OCR (optional) import guard
try:
    import fitz
    import pytesseract
    from PIL import Image
except Exception:
    fitz = None
    pytesseract = None
    Image = None


def ensure_ocr_text(conn: sqlite3.Connection, doc_id: int, original_pdf: str) -> Optional[str]:
    cur = conn.cursor()
    row = cur.execute("SELECT ocr_text FROM single_documents WHERE id=?", (doc_id,)).fetchone()
    if row and row[0]:
        return row[0]
    if not original_pdf or not os.path.exists(original_pdf):
        logging.warning(f"Doc {doc_id}: original PDF missing, cannot OCR")
        return None
    if app_config.FAST_TEST_MODE:
        logging.info(f"Doc {doc_id}: FAST_TEST_MODE enabled, skipping OCR")
        return None
    if not (fitz and pytesseract and Image):
        logging.warning(f"Doc {doc_id}: OCR libs not available, skipping")
        return None
    try:
        logging.info(f"Doc {doc_id}: Performing fallback OCR (first page only) for tagging context")
        with fitz.open(original_pdf) as doc:
            if doc.page_count == 0:
                return None
            page = doc[0]
            # Some versions of PyMuPDF expose get_pixmap; others use getPixmap.
            # Use a safe getattr to satisfy static analyzers and maintain runtime compatibility.
            pix_getter = getattr(page, 'get_pixmap', None) or getattr(page, 'getPixmap', None)
            if pix_getter is None:
                raise RuntimeError('Cannot rasterize PDF page: missing get_pixmap/getPixmap on Page')
            pix = pix_getter(matrix=fitz.Matrix(1.5, 1.5))
            img_bytes = pix.tobytes('png')
        from io import BytesIO
        with Image.open(BytesIO(img_bytes)) as im:
            text = pytesseract.image_to_string(im) or ''
        cur.execute("UPDATE single_documents SET ocr_text=? WHERE id=?", (text, doc_id))
        conn.commit()
        return text
    except Exception as e:
        logging.error(f"Doc {doc_id}: OCR failed: {e}")
        return None


def tags_already_stored(conn: sqlite3.Connection, doc_id: int) -> bool:
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(1) FROM document_tags WHERE document_id=?", (doc_id,))
        row = cur.fetchone()
        return bool(row and row[0] and row[0] > 0)
    except Exception:
        return False


def store_tags(conn: sqlite3.Connection, doc_id: int, tags: dict) -> int:
    """Store extracted tags using the existing enriched document_tags schema.

    Existing schema columns: id, document_id, tag_category, tag_value, extraction_confidence, llm_source, created_at
    We'll map our tag dict keys to tag_category and default confidence=1.0, llm_source='recovery'.
    Uses INSERT OR IGNORE to avoid duplicate (document_id, tag_category, tag_value) violations.
    """
    cur = conn.cursor()
    inserted = 0
    for tag_category, values in tags.items():
        if not values:
            continue
        for val in values:
            try:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO document_tags
                    (document_id, tag_category, tag_value, extraction_confidence, llm_source)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (doc_id, tag_category, val, 1.0, 'recovery')
                )
                if cur.rowcount > 0:
                    inserted += 1
            except sqlite3.OperationalError as oe:
                # Fallback: if table absent or different structure, attempt minimal table
                if 'no such table' in str(oe).lower():
                    cur.execute("CREATE TABLE IF NOT EXISTS document_tags (document_id INTEGER, tag_category TEXT, tag_value TEXT)")
                    cur.execute("INSERT INTO document_tags (document_id, tag_category, tag_value) VALUES (?, ?, ?)", (doc_id, tag_category, val))
                    inserted += 1
                else:
                    raise
    conn.commit()
    return inserted


def regenerate_markdown(filing_base: str, category: str, filename_base: str, markdown_content: str):
    import tempfile
    # Ensure filing_base is configured; if not, fall back to system tempdir
    if not filing_base:
        filing_base = os.environ.get('FILING_CABINET_DIR') or tempfile.gettempdir()
    category_dir = os.path.join(filing_base, category)
    os.makedirs(category_dir, exist_ok=True)
    path = os.path.join(category_dir, f"{filename_base}.md")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    logging.info(f"📝 Regenerated markdown: {path}")


def main():
    parser = argparse.ArgumentParser(description='Recover tags & markdown for an exported batch')
    parser.add_argument('--batch', '-b', type=int, required=True, help='Batch ID to recover')
    parser.add_argument('--force-regen', action='store_true', help='Force tag regeneration even if already stored')
    parser.add_argument('--skip-ocr', action='store_true', help='Skip OCR even if missing ocr_text')
    parser.add_argument('--dry-run', action='store_true', help='Do not persist changes')
    args = parser.parse_args()

    db_path = app_config.DATABASE_PATH
    if not os.path.exists(db_path):
        logging.error(f"Database not found: {db_path}")
        return 1

    # Acquire a DB connection preferring the app helper, then the dev_tools helper, then sqlite3.connect
    conn = None
    try:
        try:
            from doc_processor.database import get_db_connection
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
        except Exception:
            try:
                from doc_processor.dev_tools.db_connect import connect as db_connect
                conn = db_connect(db_path, timeout=30.0)
                conn.row_factory = sqlite3.Row
            except Exception:
                # Final fallback to direct sqlite3.connect for uncommon
                # environments where the helper isn't importable.
                conn = sqlite3.connect(db_path, timeout=30.0)
                conn.row_factory = sqlite3.Row
    except Exception as e:
        logging.error(f"Failed to open database connection: {e}")
        return 1

    cur = conn.cursor()

    # Fetch documents for batch
    cur.execute("SELECT id, original_pdf_path, searchable_pdf_path, final_category, final_filename, ai_suggested_category, ai_suggested_filename, ocr_text FROM single_documents WHERE batch_id=?", (args.batch,))
    docs = cur.fetchall()
    if not docs:
        logging.error(f"No single_documents rows found for batch {args.batch}")
        return 1

    filing_base = app_config.FILING_CABINET_DIR
    errors = 0
    processed = 0

    for doc in docs:
        doc_id, original_pdf, searchable_pdf, final_cat, final_fn, ai_cat, ai_fn, ocr_text = doc
        display_name = final_fn or ai_fn or f"document_{doc_id}"
        category = final_cat or ai_cat or 'Uncategorized'
        filename_base = display_name
        logging.info(f"Doc {doc_id}: Recovering tags for {display_name} (category={category})")

        # Ensure we have OCR text if needed
        if (not ocr_text or len(ocr_text) < 50) and not args.skip_ocr:
            ocr_text = ensure_ocr_text(conn, doc_id, original_pdf)

        if not ocr_text or len(ocr_text.strip()) < 50:
            logging.warning(f"Doc {doc_id}: Insufficient OCR text for tagging; skipping tag extraction")
            continue

        # Skip if tags already exist unless force
        if not args.force_regen and tags_already_stored(conn, doc_id):
            logging.info(f"Doc {doc_id}: Tags already stored (use --force-regen to override)")
        else:
            tags = extract_document_tags(ocr_text, display_name)
            if tags and not args.dry_run:
                inserted = store_tags(conn, doc_id, tags)
                logging.info(f"Doc {doc_id}: Stored {inserted} tags")
            elif tags:
                logging.info(f"Doc {doc_id}: (dry-run) Would store {sum(len(v) for v in tags.values())} tags")
            else:
                logging.warning(f"Doc {doc_id}: Tag extraction failed or returned none")

        # Regenerate markdown with updated tag list and AI metadata
        # Re-fetch AI metadata in case of schema updates
        detail = cur.execute("SELECT ai_confidence, ai_summary, final_category, final_filename, ai_suggested_category, ai_suggested_filename FROM single_documents WHERE id=?", (doc_id,)).fetchone()
        if detail:
            ai_conf, ai_summary, final_cat2, final_fn2, ai_cat2, ai_fn2 = detail
        else:
            ai_conf = ai_summary = final_cat2 = final_fn2 = ai_cat2 = ai_fn2 = None
        # Determine final naming again
        final_category_val = final_cat2 or final_cat or ai_cat or 'Uncategorized'
        final_filename_val = final_fn2 or final_fn or filename_base
        markdown_content = _create_single_document_markdown_content(
            original_filename=filename_base,
            category=final_category_val,
            ocr_text=ocr_text,
            extracted_tags=None,  # We'll rebuild tags from DB below for fidelity
            ai_suggested_category=ai_cat2 or ai_cat,
            ai_suggested_filename=ai_fn2 or ai_fn,
            final_category=final_cat2 or final_cat,
            final_filename=final_fn2 or final_fn,
            ai_confidence=ai_conf,
            ai_summary=ai_summary,
            rotation=None,
            ocr_dpi=None,
            rescan_events=None,
        )
        # Augment markdown by appending tags from DB (ensures canonical list)
        if not args.dry_run:
            # Pull stored tags
            try:
                tag_rows = cur.execute("SELECT tag_category, tag_value FROM document_tags WHERE document_id=?", (doc_id,)).fetchall()
            except sqlite3.OperationalError:
                tag_rows = cur.execute("SELECT tag_type, tag_value FROM document_tags WHERE document_id=?", (doc_id,)).fetchall()
            if tag_rows:
                markdown_content += "\n## 🏷️ Extracted Tags (Recovered)\n\n"
                grouped = {}
                for ttype, tval in tag_rows:
                    grouped.setdefault(ttype, []).append(tval)
                for ttype, vals in grouped.items():
                    pretty = ttype.replace('_', ' ').title()
                    markdown_content += f"**{pretty}:** {', '.join(vals)}  \n"
        if not args.dry_run:
            regenerate_markdown(filing_base, category.replace(' ', '_'), filename_base, markdown_content)
        else:
            logging.info(f"Doc {doc_id}: (dry-run) Would regenerate markdown for {filename_base}")
        processed += 1

    conn.close()
    logging.info(f"Recovery complete. Processed {processed} docs (errors={errors}).")
    return 0 if errors == 0 else 2

if __name__ == '__main__':
    sys.exit(main())

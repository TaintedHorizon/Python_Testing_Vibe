import os
import sys
from dotenv import load_dotenv
import sqlite3

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env from doc_processor subfolder
dotenv_path = os.path.join("doc_processor", ".env")
if os.path.exists(dotenv_path):
	load_dotenv(dotenv_path)
else:
	load_dotenv()

# Import after path setup
from config_manager import app_config

db_path = app_config.DATABASE_PATH
print(f"Using database: {db_path}")

import argparse

parser = argparse.ArgumentParser(description='Clear grouping/ordering for a specific batch (destructive)')
parser.add_argument('--batch', type=int, default=1, help='Batch ID to clear (default: 1)')
parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
parser.add_argument('--yes', '-y', action='store_true', help='Auto-confirm destructive action (or set CONFIRM_RESET=1)')
args = parser.parse_args()

dry_run = args.dry_run or os.getenv('DRY_RUN','0').lower() in ('1','true','t')
env_confirm = os.getenv('CONFIRM_RESET','0').lower() in ('1','true','t')
if not (env_confirm or args.yes):
	confirm = input(f"This will DELETE grouping/order data for batch {args.batch}. Type 'yes' to continue: ")
	if confirm.lower() != 'yes':
		print("Operation cancelled (no confirmation).")
		sys.exit(0)

try:
	from doc_processor.database import get_db_connection
	conn = get_db_connection()
except Exception:
	conn = sqlite3.connect(db_path, timeout=30.0)
	conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Delete all document_pages for batch 1 (including orphans)
print(f"Deleting all document_pages for batch {args.batch} (including orphans)...")
if not dry_run:
	cursor.execute("""
		DELETE FROM document_pages
		WHERE document_id IN (SELECT id FROM documents WHERE batch_id = ?)
		   OR page_id IN (SELECT id FROM pages WHERE batch_id = ?)
	""", (args.batch, args.batch))
else:
	print("DRY-RUN: would execute deletion from document_pages")

# Delete all documents for batch
print(f"Deleting all documents for batch {args.batch}...")
if not dry_run:
	cursor.execute("DELETE FROM documents WHERE batch_id = ?", (args.batch,))
else:
	print("DRY-RUN: would delete documents for batch")

if not dry_run:
	conn.commit()
	print(f"Grouping and ordering for batch {args.batch} have been cleared. Page verification state is unchanged.")
else:
	print("DRY-RUN: no changes were made.")
conn.close()

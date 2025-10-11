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

try:
	from doc_processor.database import get_db_connection
	conn = get_db_connection()
except Exception:
	conn = sqlite3.connect(db_path, timeout=30.0)
	conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("\nAll document_pages for batch 1 (even if orphaned):")
cursor.execute("""
	SELECT dp.* FROM document_pages dp
	LEFT JOIN documents d ON dp.document_id = d.id
	WHERE d.batch_id = 1 OR d.batch_id IS NULL
""")
for row in cursor.fetchall():
	print(row)

print("\nPages for batch 1 NOT referenced in document_pages:")
cursor.execute("""
	SELECT p.id, p.status, p.human_verified_category FROM pages p
	LEFT JOIN document_pages dp ON p.id = dp.page_id
	WHERE p.batch_id = 1 AND dp.page_id IS NULL
""")
for row in cursor.fetchall():
	print(row)

conn.close()

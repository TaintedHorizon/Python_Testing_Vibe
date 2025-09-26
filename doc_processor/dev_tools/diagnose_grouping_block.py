import os
from dotenv import load_dotenv
import sqlite3

# Load .env from doc_processor subfolder
dotenv_path = os.path.join("doc_processor", ".env")
if os.path.exists(dotenv_path):
	load_dotenv(dotenv_path)
else:
	load_dotenv()

db_path = os.getenv("DATABASE_PATH")
if not db_path:
	db_path = "/home/svc-scan/Python_Testing_Vibe/doc_processor/documents.db"  # fallback

print(f"Using database: {db_path}")

conn = sqlite3.connect(db_path)
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

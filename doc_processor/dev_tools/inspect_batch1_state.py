
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
	db_path = "doc_processor/documents.db"  # fallback

print(f"Using database: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\nBatch status:")
cursor.execute("SELECT id, status FROM batches WHERE id = 1")
for row in cursor.fetchall():
	print(row)

print("\nPages for batch 1:")
cursor.execute("SELECT id, status, human_verified_category, rotation_angle FROM pages WHERE batch_id = 1")
for row in cursor.fetchall():
	print(row)

print("\nDocuments for batch 1:")
cursor.execute("SELECT id, final_filename_base FROM documents WHERE batch_id = 1")
for row in cursor.fetchall():
	print(row)

print("\nDocument pages for batch 1:")
cursor.execute("SELECT dp.id, dp.document_id, dp.page_id, dp.sequence FROM document_pages dp JOIN documents d ON dp.document_id = d.id WHERE d.batch_id = 1")
for row in cursor.fetchall():
	print(row)

conn.close()

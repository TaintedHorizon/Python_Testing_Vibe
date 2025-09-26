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

# Delete all document_pages for batch 1 (including orphans)
print("Deleting all document_pages for batch 1 (including orphans)...")
cursor.execute("""
	DELETE FROM document_pages
	WHERE document_id IN (SELECT id FROM documents WHERE batch_id = 1)
	   OR page_id IN (SELECT id FROM pages WHERE batch_id = 1)
""")

# Delete all documents for batch 1
print("Deleting all documents for batch 1...")
cursor.execute("DELETE FROM documents WHERE batch_id = 1")

conn.commit()
conn.close()
print("Grouping and ordering for batch 1 have been cleared. Page verification state is unchanged.")

import os
from dotenv import load_dotenv
from doc_processor.database import reset_batch_to_start

# Load environment variables (for DATABASE_PATH)
load_dotenv()

# Reset batch 1
reset_batch_to_start(1)
print("Batch 1 has been fully reset.")

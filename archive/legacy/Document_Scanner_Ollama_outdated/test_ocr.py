import easyocr
import warnings
import sys

# Suppress a harmless warning to keep the output clean
warnings.filterwarnings("ignore", message=".*'pin_memory' argument is set as true.*")

print("--- Step 1: Initializing EasyOCR Reader ---")
try:
    reader = easyocr.Reader(['en'])
    print("--- SUCCESS: EasyOCR Reader initialized successfully! ---")
except Exception as e:
    print(f"--- FAILED: Could not initialize EasyOCR Reader. Error: {e} ---")
    sys.exit(1)

# The absolute path to the test image you just created
image_path = '/mnt/scans_intake/test_page-01.png'
print(f"\n--- Step 2: Reading text from '{image_path}' ---")

try:
    result = reader.readtext(image_path, detail=0, paragraph=True)
    print("--- SUCCESS: OCR completed! ---")

    print("\n--- Extracted Text ---")
    for line in result:
        print(line)

except Exception as e:
    print(f"--- FAILED: Could not read text from image. Error: {e} ---")

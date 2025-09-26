# Requirements Documentation

## doc_processor/requirements.txt

This file contains all dependencies needed for the document processing system.

### Core Dependencies:
- **Flask**: Web framework for the user interface
- **python-dotenv**: Configuration management from .env files
- **easyocr**: Primary OCR engine for text extraction
- **pytesseract**: Secondary OCR tool and orientation detection
- **PyMuPDF (fitz)**: Fast PDF text extraction and manipulation
- **pdf2image**: PDF to image conversion
- **Pillow**: Image processing library
- **numpy**: Numerical computing for image data
- **opencv-python-headless**: Computer vision algorithms (EasyOCR dependency)
- **requests**: HTTP client for API communication
- **ollama**: Official client for Ollama LLM server
- **SQLAlchemy**: Database ORM (optional, but included for future use)
- **pytest**: Testing framework

### Version Strategy:
- Uses minimum version constraints (>=) to allow for security updates
- Tested with the specified minimum versions
- All packages are actively maintained and regularly updated

### Installation:
```bash
cd doc_processor
source venv/bin/activate
pip install -r requirements.txt
```

### System Dependencies:
In addition to Python packages, the system requires:
- **tesseract-ocr**: System package for OCR functionality
- **poppler-utils**: System package for PDF processing
- **sqlite3**: Usually included with Python

### Testing:
Run `python -m pip check` to verify no dependency conflicts exist.
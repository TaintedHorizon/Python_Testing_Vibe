# AI Assistant Instructions for Python_Testing_Vibe

## Project Overview
This is a human-in-the-loop document processing system built with Python. The core functionality is split across multiple specialized modules:

- `doc_processor/app.py`: Flask web application handling routes and UI orchestration
- `doc_processor/processing.py`: Core document processing engine (OCR, AI integration, file handling)
- `doc_processor/database.py`: Data access layer for SQLite operations
- `doc_processor/templates/`: HTML templates for web interface

## Key Architecture Patterns

### Document Processing Pipeline
1. Intake → OCR → AI Classification → Human Verification → Grouping → Ordering → Export
2. Each stage has clear boundaries and state management in SQLite
3. Example: `processing.py:process_batch()` orchestrates the initial automated steps

### Database Operations
- All SQL operations centralized in `database.py`
- Use context managers for connections: 
```python
with database_connection() as conn:
    cursor = conn.cursor()
```

### AI Integration
- Local LLM via Ollama API for document classification
- Example prompt structure in `processing.py:get_ai_classification()`
- AI responses always validated against known categories

## Critical Workflows

### Environment Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python doc_processor/database_setup.py
```

### Configuration
- Copy `.env.sample` to `.env` and configure:
  - Directory paths (INTAKE_DIR, PROCESSED_DIR, etc.)
  - Ollama settings (OLLAMA_HOST, OLLAMA_MODEL)
  - Debug flags (DEBUG_SKIP_OCR)

### Development Flow
1. Start Flask server: `cd /home/svc-scan/Python_Testing_Vibe && ./start_app.sh`
2. Access UI at `http://localhost:5000`
3. Place test PDFs in configured INTAKE_DIR
4. Follow Batch Control workflow for processing

## Project-Specific Conventions

### Error Handling
- All file operations wrapped in try/except with logging
- Database errors bubble up to route handlers
- Example pattern in `processing.py:_process_single_page_from_file()`

### State Management
- Document status tracked via SQLite
- Status constants defined in `config.py`
- Batch-level and page-level status tracking

### File Organization
- Processed files moved to categorized directories
- Naming convention: `YYYY-MM-DD_Descriptive-Name`
- Original PDFs archived separately

## Integration Points

### External Dependencies
1. Ollama API for AI/LLM
2. EasyOCR/Tesseract for text extraction
3. pdf2image for PDF processing

### Cross-Component Communication
- Flask routes → Database queries → Template rendering
- Processing jobs update database → UI polls for completion

## Testing & Debugging
- Set DEBUG_SKIP_OCR=true to bypass OCR during development
- Monitor `processing.py` logs for pipeline issues
- Database can be reset via `reset_environment.py`
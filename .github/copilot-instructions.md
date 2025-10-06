# AI Assistant Instructions for Python_Testing_Vibe

## ⚠️ CRITICAL: Common Mistakes to Avoid

### 🚨 **ALWAYS Use These Correct Patterns:**

#### **✅ Application Startup (NEVER run Flask directly!)**
```bash
# CORRECT - Use the provided startup script
cd /home/svc-scan/Python_Testing_Vibe && ./start_app.sh

# INCORRECT - These will fail!
# python app.py                    ❌ Wrong - import errors
# cd doc_processor && python app.py ❌ Wrong - import errors  
# python -m doc_processor.app      ❌ Wrong - must be from repo root
```

#### **✅ Virtual Environment Location**
```bash
# CORRECT - venv is inside doc_processor/
cd /home/svc-scan/Python_Testing_Vibe/doc_processor
source venv/bin/activate

# INCORRECT - These locations don't exist!
# source .venv/bin/activate        ❌ Wrong location
# source venv/bin/activate         ❌ Wrong - not in repo root
```

#### **✅ Environment Name - It's "venv" NOT "doc_processor_env"**
```bash
# CORRECT - Virtual environment is named "venv"
source doc_processor/venv/bin/activate

# INCORRECT - This environment name doesn't exist!
# source doc_processor_env/bin/activate  ❌ Wrong name
```

#### **✅ Configuration Management - Use config_manager.py**
```python
# CORRECT - Use the centralized config system
from config_manager import app_config
intake_dir = app_config.INTAKE_DIR
ollama_host = app_config.OLLAMA_HOST

# INCORRECT - Don't reference old config.py!
# from config import INTAKE_DIR      ❌ Wrong - file doesn't exist
# import config                      ❌ Wrong - old pattern
```

#### **✅ Database Operations**
```python
# CORRECT - Use the established pattern
from database import database_connection
with database_connection() as conn:
    cursor = conn.cursor()
    # ... database operations
```

## Project Overview
This is a human-in-the-loop document processing system with a **modular Flask Blueprint architecture**. The system was completely refactored from a monolithic design to eliminate maintenance issues.

For a layered breakdown and full file map, see `../ARCHITECTURE.md` and the Comprehensive File Map table in the root `README.md`.

> Quick Reference: A complete file/layer map now lives in `ARCHITECTURE.md` (root) and the root `README.md` under "Comprehensive File Map". Use those when you need to locate modules or justify code placement.

### Core Architecture (Post-Refactoring)
- **`doc_processor/app.py`**: Main Flask application factory with Blueprint registration (309 lines)
- **`doc_processor/routes/`**: 6 specialized Blueprint modules (intake, batch, manipulation, export, admin, api)
- **`doc_processor/services/`**: Business logic layer (document_service, batch_service, export_service)
- **`doc_processor/config_manager.py`**: Centralized configuration with type safety and validation
- **`doc_processor/database.py`**: Data access layer for SQLite operations
- **`doc_processor/processing.py`**: Core document processing engine (OCR, AI integration)

### Recent Major Updates (October 2025)
- **🎯 PDF Display Standardization**: All templates now use consistent iframe approach with automatic image-to-PDF conversion
- **🏗️ Blueprint Architecture**: Modular design with 89% code reduction from monolithic version
- **🔧 API Compatibility**: All endpoints restored to match original functionality exactly

## Critical Workflows

### **Environment Setup (Follow Exactly!)**
```bash
# 1. Navigate to doc_processor subdirectory
cd /home/svc-scan/Python_Testing_Vibe/doc_processor

# 2. Create virtual environment (if doesn't exist)
python3 -m venv venv

# 3. Activate virtual environment
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Set up database (if needed)
python dev_tools/database_setup.py
```

### **Configuration (Essential Steps)**
```bash
# 1. Copy sample environment file
cd /home/svc-scan/Python_Testing_Vibe/doc_processor
cp .env.sample .env

# 2. Edit .env with your settings:
#    - INTAKE_DIR=intake
#    - PROCESSED_DIR=processed  
#    - FILING_CABINET_DIR=filing_cabinet
#    - OLLAMA_HOST=http://localhost:11434
#    - OLLAMA_MODEL=llama3.1:8b
#    - DEBUG_SKIP_OCR=false
```

### **Starting the Application (The Only Correct Way)**
```bash
# Always use the startup script from repo root
cd /home/svc-scan/Python_Testing_Vibe
./start_app.sh

# This script automatically:
# 1. Activates the correct venv (doc_processor/venv)
# 2. Changes to repo root directory
# 3. Runs: python -m doc_processor.app
# 4. Provides colored output and error checking
```

### **Development Commands (Common Tasks)**
```bash
# Terminal-based operations - always activate venv first:
cd /home/svc-scan/Python_Testing_Vibe/doc_processor
source venv/bin/activate

# Then run any Python scripts:
python dev_tools/database_setup.py
python test_complete_workflow.py
python dev_tools/diagnose_grouping_block.py

# For Flask routes testing, always use the startup script
```

## Key Architecture Patterns

### Document Processing Pipeline
1. **Intake** → **Analysis** (OCR + AI) → **Human Verification** → **Grouping/Ordering** → **Export**
2. **Image-to-PDF Conversion**: All images automatically converted to PDF during analysis for consistent display
3. **State Management**: Each stage tracked in SQLite with caching for interrupted operations
4. **Template Unification**: All 5 preview templates use identical iframe approach

### Configuration System (config_manager.py)
```python
# Always import from config_manager, never from old config.py
from config_manager import app_config

# Available configuration options:
app_config.INTAKE_DIR           # Input directory path
app_config.PROCESSED_DIR        # Working directory path
app_config.FILING_CABINET_DIR   # Final output directory
app_config.OLLAMA_HOST          # LLM service host
app_config.OLLAMA_MODEL         # LLM model name
app_config.DEBUG_SKIP_OCR       # Skip OCR for debugging
app_config.LOG_FILE_PATH        # Application log location
```

### Database Operations
```python
# Standard pattern for all database operations
from database import database_connection
with database_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM batches WHERE status = ?", (status,))
    results = cursor.fetchall()
```

### AI/LLM Integration  
```python
# Import from the correct module
from llm_utils import get_ai_document_type_analysis

# LLM operations use config_manager settings
result = get_ai_document_type_analysis(
    file_path, content_sample, filename, page_count, file_size_mb
)
```

## Blueprint Architecture (Route Organization)

### Route Modules (`doc_processor/routes/`)
- **`intake.py`**: File analysis, document detection, intake processing
- **`batch.py`**: Batch control, processing orchestration, status tracking
- **`manipulation.py`**: Document editing, verification, grouping, ordering
- **`export.py`**: Export workflows, finalization, file serving
- **`admin.py`**: System administration, configuration, category management
- **`api.py`**: REST endpoints, AJAX support, real-time progress

### Service Layer (`doc_processor/services/`)
- **`document_service.py`**: Core document business logic
- **`batch_service.py`**: Batch processing orchestration
- **`export_service.py`**: Export and finalization logic

## Project-Specific Conventions

### File Organization
- **Intake**: `/home/svc-scan/Python_Testing_Vibe/doc_processor/intake/`
- **Processing**: `/home/svc-scan/Python_Testing_Vibe/doc_processor/processed/`
- **Final Storage**: `/home/svc-scan/Python_Testing_Vibe/doc_processor/filing_cabinet/`
- **Logs**: `/home/svc-scan/Python_Testing_Vibe/doc_processor/logs/`
- **Database**: `/home/svc-scan/Python_Testing_Vibe/doc_processor/documents.db`

### Error Handling Patterns
```python
# Standard logging pattern
import logging
logger = logging.getLogger(__name__)

try:
    # File operations
    result = process_document(file_path)
    logger.info(f"✅ Successfully processed: {file_path}")
except Exception as e:
    logger.error(f"❌ Processing failed for {file_path}: {e}")
    # Handle gracefully
```

### Status Management
```python
# Use config_manager constants
from config_manager import app_config

status = app_config.STATUS_PENDING_VERIFICATION
status = app_config.STATUS_VERIFICATION_COMPLETE
```

## Integration Points

### External Dependencies
1. **Ollama API**: Local LLM for document classification (configured via `config_manager.py`)
2. **EasyOCR/Tesseract**: Text extraction from images and PDFs
3. **pdf2image**: PDF to image conversion for processing
4. **PIL (Pillow)**: Image-to-PDF conversion for display standardization

### PDF Display System (October 2025 Update)
- **All templates** use iframe approach for consistent document display
- **Images automatically converted** to PDF during analysis for unified viewing
- **Smart file serving** via `export.serve_original_pdf` route
- **Rotation system** standardized across all preview templates

## Testing & Debugging

### Development Tools (in `dev_tools/`)
```bash
# Always activate venv first
cd /home/svc-scan/Python_Testing_Vibe/doc_processor
source venv/bin/activate

# Common debugging tools
python dev_tools/database_setup.py          # Reset database
python dev_tools/diagnose_grouping_block.py # Debug batch issues
python dev_tools/reset_environment.py       # Full system reset
python test_complete_workflow.py            # Test PDF conversion workflow
```

### Configuration Debugging
- **Set `DEBUG_SKIP_OCR=true`** in `.env` to bypass OCR during development
- **Monitor logs** at `doc_processor/logs/app.log`  
- **Check configuration** loading in `config_manager.py`

### Common Issues
1. **Import Errors**: Always run from repo root with module syntax
2. **Database Lock**: Use `database_connection()` context manager
3. **OCR Timeout**: Adjust `OLLAMA_TIMEOUT` in `.env`
4. **File Not Found**: Check paths are relative to `doc_processor/` directory

## ⚠️ Anti-Patterns (What NOT to Do)

### ❌ **Don't Do These:**
```bash
# DON'T: Run Flask directly
python app.py                              # Fails with import errors

# DON'T: Use wrong directory structure  
cd Python_Testing_Vibe && python app.py    # Wrong location

# DON'T: Reference non-existent paths
source .venv/bin/activate                   # Wrong venv location
from config import SETTING                 # config.py doesn't exist

# DON'T: Skip the startup script
python -m doc_processor.app                # Must be from repo root with script
```

### ✅ **Always Do These:**
```bash
# DO: Use the startup script
./start_app.sh                             # Handles everything correctly

# DO: Use correct venv location
source doc_processor/venv/bin/activate     # Correct location

# DO: Use config_manager for settings
from config_manager import app_config      # Modern config system
```

## Summary for AI Assistants

**🎯 Key Takeaways:**
1. **Always use `./start_app.sh`** for running the Flask application
2. **Virtual environment is at `doc_processor/venv/`** - not elsewhere
3. **Use `config_manager.py`** for all configuration - not old `config.py`
4. **All paths are relative to `doc_processor/`** directory
5. **Templates now use unified PDF iframe display** with automatic image conversion
6. **Blueprint architecture** means routes are organized in `routes/` subdirectory
7. **Always activate venv before running any Python scripts** in `doc_processor/`

These patterns eliminate the most common issues when working with this codebase.
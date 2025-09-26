
# Python_Testing_Vibe

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A multi-purpose development repository containing various Python projects and utilities, with a focus on document processing and system administration tools.

## Repository Structure

### 🏠 Main Projects

#### **`doc_processor/`** - Human-in-the-Loop Document Processing System
Production-ready document processing pipeline with AI integration, human verification, and complete audit trails.

**Key Features:**
- End-to-end document workflow: Intake → OCR → AI Classification → Human Verification → Export
- LLM-powered document analysis with Ollama integration
- Complete file safety with rollback mechanisms
- RAG-ready data structure for future AI integration
- Modern Flask web interface with guided workflows

**Status:** ✅ Production Ready  
**Tech Stack:** Python 3, Flask, SQLite, Ollama LLM, EasyOCR/Tesseract

[📖 Full Documentation](doc_processor/readme.md)

### 🛠️ Utility Tools (`tools/`)

#### **`download_manager/`**
Download management utilities with GUI interface for batch file operations.

#### **`file_utils/`**
File manipulation utilities including regex-based copy operations.

#### **`gamelist_editor/`**
XML gamelist editor for retro gaming collections and metadata management.

#### **`sdcard_imager/`**
SD card imaging utility for backup and restoration operations.

### 🗂️ Working Directories

#### **Document Processing Directories**
- **`intake/`** - Incoming PDFs for processing
- **`processed/`** - Work-in-progress document staging
- **`archive/`** - Processed file archives
- **`filing_cabinet/`** - Final categorized document storage
- **`logs/`** - Application and system logs

#### **Development Infrastructure**
- **`instance/`** - Flask application instance data
- **`.venv/`** - Python virtual environment
- **`.github/`** - GitHub workflows and repository configuration

### 📚 Legacy & Experimental

#### **`Document_Scanner_Gemini_outdated/`**
Legacy document scanner implementation using Google Gemini API.
*Status: Archived - superseded by doc_processor*

#### **`Document_Scanner_Ollama_outdated/`**
Legacy document scanner using Ollama integration.
*Status: Archived - superseded by doc_processor*

## Quick Start

### For Document Processing:
```bash
cd doc_processor
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python dev_tools/database_setup.py
cp .env.sample .env  # Edit with your settings
python app.py
```

Access the web interface at `http://localhost:5000`

### For Utility Tools:
```bash
cd tools/<specific_tool>
# Follow individual tool documentation
```

## Development Setup

1. **Clone Repository:**
   ```bash
   git clone https://github.com/TaintedHorizon/Python_Testing_Vibe.git
   cd Python_Testing_Vibe
   ```

2. **Choose Your Project:**
   - **Document Processing**: See `doc_processor/readme.md`
   - **Utilities**: Browse `tools/` directory
   - **Development**: Use existing `.venv/` or create project-specific environments

3. **Environment Management:**
   ```bash
   # Use existing environment
   source .venv/bin/activate
   
   # Or create project-specific environment
   cd <project_directory>
   python -m venv venv
   source venv/bin/activate
   ```

## Project Status

| Component | Status | Description |
|-----------|--------|-------------|
| **doc_processor** | ✅ Production | Full-featured document processing system |
| **tools/download_manager** | ✅ Stable | Download management with GUI |
| **tools/file_utils** | ✅ Stable | File manipulation utilities |
| **tools/gamelist_editor** | ✅ Stable | XML gamelist management |
| **tools/sdcard_imager** | ✅ Stable | SD card imaging utility |
| **Document_Scanner_*_outdated** | 🗄️ Archived | Legacy implementations |

## Contributing

Contributions are welcome! Each project maintains its own contributing guidelines:

- **doc_processor**: See `doc_processor/CONTRIBUTING.md`
- **General**: Follow standard Python conventions and add tests where applicable

## License

This repository is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Credits

- **@TaintedHorizon** - Primary maintainer and developer
- Individual tools may have additional contributors documented in their respective directories

---

*This repository serves as both a development playground and a collection of production-ready utilities. The main focus is the document processing system in `doc_processor/`, with various supporting tools in `tools/`.*

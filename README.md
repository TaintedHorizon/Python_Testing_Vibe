
# Python_Testing_Vibe

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A multi-purpose development repository containing various Python projects and utilities, with a focus on document processing and system administration tools.

## Repository Structure

### 🏠 Main Projects

#### **`doc_processor/`** - Human-in-the-Loop Document Processing System
Production-ready document processing pipeline with AI integration, human verification, and complete audit trails.

**🎉 MAJOR ARCHITECTURE UPDATE (October 2025):**
- **Completely refactored from monolithic to modular architecture**
- **89% code reduction**: From 2,947-line single file to 309-line main app + 13 focused modules
- **Zero indentation errors**: Eliminated editing issues with small, focused files
- **Professional Blueprint architecture**: Clean separation of concerns for enterprise-grade maintainability
- **✅ API COMPATIBILITY RESTORED**: All Blueprint routes now match original functionality exactly
- **🔧 MAJOR FIX (Oct 1, 2025)**: Fixed critical API contract differences between original and Blueprint implementations

**Key Features:**
- End-to-end document workflow: Intake → OCR → AI Classification → Human Verification → Export
- **Enhanced Single Document Workflow**: Streamlined processing with AI-powered category and filename suggestions
- **Intelligent AI Filename Generation**: Content-based filename suggestions using document analysis
- **Interactive Manipulation Interface**: Edit AI suggestions with dropdown categories and filename options
- **Individual Document Rescan**: Re-analyze specific documents for improved AI results
- LLM-powered document analysis with Ollama integration
- Complete file safety with rollback mechanisms
- RAG-ready data structure for future AI integration
- Modern Flask web interface with guided workflows
- **Modular Blueprint Architecture**: 6 route modules + 3 service layers for maximum maintainability

**Architecture:**
- **Modular Design**: Routes organized by functionality (intake, batch, manipulation, export, admin, api)
- **Service Layer**: Separate business logic from web interface concerns
- **Clean Imports**: Proper Python package structure with relative imports
- **Maintainable**: Small, focused files instead of massive monolithic code

**Status:** ✅ Production Ready  
**Tech Stack:** Python 3, Flask Blueprints, SQLite, Ollama LLM, EasyOCR/Tesseract

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

All document processing directories are now properly organized within `doc_processor/`:

#### **Document Processing Directories** (in `doc_processor/`)
- **`intake/`** - Incoming PDFs for processing
- **`processed/`** - Work-in-progress document staging
- **`archive/`** - Processed file archives
- **`filing_cabinet/`** - Final categorized document storage
- **`logs/`** - Application and system logs
- **`instance/`** - Flask application instance data
- **`venv/`** - Python virtual environment

#### **Repository Infrastructure**
- **`.github/`** - GitHub workflows and repository configuration

### 📚 Legacy & Experimental

#### **`Document_Scanner_Gemini_outdated/`** (260KB)
Legacy document scanner implementation using Google Gemini API.  
*Status: Archived - superseded by doc_processor (source code only, venv removed)*

#### **`Document_Scanner_Ollama_outdated/`** (164KB)
Legacy document scanner using Ollama integration.  
*Status: Archived - superseded by doc_processor (source code only, venv removed)*

## Quick Start

### For Document Processing:
```bash
cd doc_processor
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python dev_tools/database_setup.py
cp .env.sample .env  # Edit with your settings

# Run the application (from project root)
cd ..
python_testing_vibe/doc_processor/venv/bin/python -m doc_processor.app
```

Access the web interface at `http://localhost:5000`

**Note:** The application now uses a proper Python package structure. Always run from the project root using the module syntax for correct import resolution.

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

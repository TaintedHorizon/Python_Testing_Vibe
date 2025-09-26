# Changelog

All notable changes to this project will be documented in this file.


## [Unreleased]

## [2025-09-26-2] - Single Document Workflow Enhancement
### Added
- **AI-Powered Filename Generation**: Implemented intelligent filename suggestions based on document content analysis
- **Enhanced Manipulation Interface**: Complete redesign of single document editing with category dropdowns and filename options
- **Individual Document Rescan**: Added rescan buttons for re-analyzing documents with low confidence or failed AI results
- **Three Filename Options**: Original filename, AI-generated content-based filename, and custom user input
- **Category Management Integration**: Manipulation interface now uses same category dropdown system as verify workflow
- **Real-time AI Analysis**: JSON-based AI responses with proper parsing and fallback mechanisms
- **Content-Based Naming**: AI analyzes OCR text to generate meaningful filenames instead of using original names
- **Rescan API Endpoint**: `/api/rescan_document/<doc_id>` for individual document re-analysis
- **Enhanced AI Prompting**: Improved prompts for better category classification and filename generation

### Changed
- **Manipulation Save Logic**: Now properly saves to `final_category` and `final_filename` instead of overwriting AI suggestions
- **Button Display Logic**: Conditional showing of "Manipulate" vs "Export" buttons based on manipulation status
- **AI Response Processing**: Enhanced JSON parsing with content-based filename generation fallbacks
- **Template Design**: Modern card-based layout for manipulation interface with better UX
- **Filename Generation**: AI now creates descriptive filenames based on document content analysis
- **Processing Pipeline**: Fixed `_get_ai_suggestions_for_document()` to use proper JSON-based AI queries

### Fixed
- **AI Filename Generation Bug**: Fixed function to generate real content-based filenames instead of just removing extensions
- **Manipulation State Tracking**: Added `has_been_manipulated` flag to properly track document editing status
- **Category Dropdown Integration**: Manipulation interface now properly integrates with global category system
- **Save Workflow**: Simplified save process - single "Save Changes" button returns to batch control
- **Template Confusion**: Removed confusing multiple action buttons, streamlined to clear sequential workflow
- **AI Analysis Display**: Removed misleading "AI Suggested" filename display when no real AI analysis occurred

### Developer / Infrastructure
- **Regeneration Script**: Added `dev_tools/regenerate_ai_suggestions.py` for updating existing documents with enhanced AI analysis
- **API Documentation**: Enhanced rescan endpoint with proper error handling and JSON responses
- **Template Components**: Modular JavaScript for handling category dropdowns and rescan functionality
- **Database Queries**: Optimized manipulation status detection with efficient SQL queries
- **Error Handling**: Comprehensive error handling for AI analysis failures and rescan operations

### UX Improvements
- **Clear Workflow Progression**: "Manipulate → Save → Export" with appropriate button visibility
- **Visual Feedback**: Loading states for rescan operations with progress indicators
- **Intelligent Defaults**: AI-suggested filenames selected by default when meaningful
- **Consistent Interface**: Manipulation dropdowns match verify page patterns for familiarity
- **Content Analysis Display**: Clear indication when filenames are based on document content vs original names

## [2025-09-26] - Major LLM Integration & File Safety Update
### Added
- **Complete LLM Functionality Restoration**: Fixed broken document type analysis with comprehensive OCR fallback for scanned documents
- **Advanced File Safety System**: Implemented `safe_move()` operations with verification and automatic rollback on failures
- **Single Document Processing Fix**: Corrected workflow to send single documents to category folders (not archive)
- **Comprehensive Logging System**: Added emoji-based logging identifiers (🤖 🌐 ✅ ❌ 💥 📄) for easy troubleshooting
- **Smart Document Detection**: Enhanced LLM-powered detection between single documents and batch scans
- **File Safety Monitoring**: Added `/api/file_safety_check` endpoint and `verify_no_file_loss()` function
- **Database Path Consistency**: Fixed duplicate `doc_processor/doc_processor/` directory creation with absolute paths
- **Modern Single Document Workflow**: All single documents now use `_process_single_documents_as_batch()` for consistent processing

### Changed
- **Configuration Management**: Enhanced with quote-stripping and fallback to `doc_processor/.env` location
- **Document Processing**: Unified all single document processing to use modern workflow instead of legacy archive-based approach
- **PDF Content Extraction**: Fixed broken content sampling in `document_detector.py` with proper OCR fallback
- **LLM Integration**: Restored `get_ai_document_type_analysis()` function with comprehensive error handling
- **Export Safety**: Added rollback mechanisms for export operations with verification of file integrity

### Fixed
- **Critical LLM Analysis Bug**: Content extraction was returning empty strings, breaking all AI classification
- **Single Document Routing**: Legacy workflow incorrectly moved single documents to archive instead of category folders
- **Configuration Loading**: Quote handling and path resolution issues in environment variable processing
- **Database Path Duplication**: Relative paths causing duplicate directories when working directory changed
- **Missing OCR Fallback**: Scanned documents with no extractable text now properly trigger OCR processing
- **File Movement Safety**: Replaced basic file operations with verified moves and rollback capabilities

### Developer / Infrastructure
- **Deprecated Legacy Functions**: Added warnings to `process_single_document()` as it incorrectly uses archive workflow
- **Enhanced Error Handling**: Comprehensive logging throughout LLM and processing pipelines
- **Test Scripts**: Added verification scripts for single document workflow and database path consistency
- **Configuration Validation**: Improved `.env` loading with better error messages and fallback handling
- **File Safety Verification**: Created monitoring tools to ensure no PDFs are lost during processing

### Documentation
- **Updated README**: Enhanced with current feature set, LLM integration details, and file safety information
- **Added Audit Trail Documentation**: Comprehensive RAG-ready data structure explanation
- **Enhanced Setup Instructions**: Updated with current configuration requirements and troubleshooting
- **File Safety Guidelines**: Added documentation for rollback mechanisms and safety verification

## [2025-09-24]
### Added
- Category Management UI (`/categories`) with: add, soft delete/restore, rename (tracks previous name), notes field, active/inactive filtering.
- Category change history (`category_change_log`) + drill-down filter (limit & category_id) and integration into `interaction_log` as structured JSON events.
- Optional rename backfill toggle (No backfill) to preserve historical page categories if desired.
- Category sorting (name/id) on management screen with dynamic buttons.
- Batch audit trail view (`/batch_audit/<batch_id>`) surfacing full interaction timeline.
- One-time structured database startup log (JSON) including path, size, mtime, permissions.
- `/update_rotation` endpoint for asynchronous rotation persistence.
- Dynamic primary action button on Verify page (Approve & Next vs Correct & Next) simplifying UX.

### Changed
- `rerun_ocr_on_page` rotation handling: now rotates in-memory only (no permanent file overwrite) preventing double-rotation confusion.
- Verify & Review pages now rely on persisted `rotation_angle` plus client transform—removed destructive image mutation.
- Logging enhancements: category changes and rotation updates recorded as `human_correction` or `category_change` events with JSON payloads.

### Fixed
- Missing Categories nav link layout alignment (converted navbar to flex, removed float issues).
- Rotation persistence gaps causing orientation reset after OCR re-run.
- Nonexistent `/update_rotation` endpoint referenced by UI (now implemented).

### Developer / Schema
- Added new columns to `categories`: `is_active`, `previous_name`, `notes` (idempotent upgrade script logic).
- Added `category_change_log` table for immutable historical events.
- Safe upgrade path via `dev_tools/database_upgrade.py` (re-runnable).

### Notes
- Historical pages retain original categories unless rename backfill selected.
- Interaction log entries now suitable for future RAG / analytics pipelines.

## [2025-09-23]
- Major project cleanup and reorganization.
- Moved all dev/admin scripts to `dev_tools/`.
- Removed obsolete and duplicate files.
- Improved documentation and project structure.

## [Earlier]
- Initial implementation of document processing pipeline.
- Added Flask web interface and SQLite integration.
- Integrated OCR and AI classification.

# Changelog

All notable changes to this project will be documented in this file.


## [Unreleased]

## [2025-09-30] - Export Naming Standardization
### Fixed
- **Export Naming Consistency**: Standardized directory and filename sanitization across single document and batch export workflows
  - Both export types now use underscores instead of spaces in directory names for better filesystem compatibility
  - Consistent filename sanitization using `security.sanitize_filename()` for all user inputs
  - Directory names: spaces → underscores, only alphanumeric + hyphens/underscores allowed
  - Filenames: non-alphanumeric characters → underscores (except dots and hyphens)
  - Applied sanitization to user input routes (`/api/set_name`, finalize form) for consistency
  - Removed duplicate internal `_sanitize_filename()` function in favor of centralized security module

### Added
- **Filing Cabinet Cleanup Tool**: New utility to standardize existing directory and file names in the filing cabinet
  - `dev_tools/cleanup_filing_cabinet_names.py` - Comprehensive cleanup utility with preview, backup, and rollback features
  - Dry-run mode to preview changes before applying them
  - Automatic backup creation before making any modifications
  - Conflict resolution for duplicate names after sanitization
  - Rollback capability to undo all changes if needed
  - Detailed logging and operation tracking
  - See `dev_tools/FILING_CABINET_CLEANUP.md` for usage instructions

## [2025-09-29-2] - Document Detection Enhancement & Rotation Support & Cleanup Automation
### Added
- **Multi-Point Document Sampling**: Enhanced document detection to sample first, middle, and last pages for better batch scan detection
  - 1 page: samples page 1 only
  - 2 pages: samples first + last page  
  - 3+ pages: samples first + middle + last page
- **Automatic Rotation Detection**: Implemented OCR confidence-based rotation detection for single documents
  - Tests all 4 orientations (0°, 90°, 180°, 270°) during processing
  - Uses OCR confidence scores and text length heuristics to determine optimal rotation
  - Automatically applies best rotation during document processing
- **Manual Rotation Controls**: Added comprehensive rotation interface to single document workflow
  - Visual rotation buttons (Rotate Left, Rotate Right, Reset) in manipulation interface
  - Real-time rotation status tracking with pending/applied states
  - Apply button for confirming rotation changes
  - Integration with existing single document manipulation workflow
- **Document Boundary Detection**: Enhanced LLM prompts to detect multiple documents scanned together
  - Identifies format inconsistencies between sample pages
  - Detects company/letterhead changes across pages
  - Recognizes topic discontinuity and document type transitions
- **Batch Directory Cleanup**: Automated cleanup of empty batch directories after export completion
  - Recursive empty directory detection with safety checks
  - Automatic cleanup after successful batch exports
  - Manual cleanup tool for maintenance: `dev_tools/cleanup_empty_batch_directories.py`
  - Audit logging of all cleanup actions

### Enhanced
- **Document Detection Accuracy**: Multi-point sampling prevents misclassification of batch scans as single documents
  - Example: 9-page file with Invoice A + Invoice B + Personal Letter now correctly detected as batch scan
  - LLM receives samples from multiple pages to identify document boundaries
- **Single Document Processing**: Added rotation detection to processing pipeline
  - Integrated into `create_searchable_pdf()` function
  - Logs rotation decisions and confidence scores
  - Preserves original files while applying optimal orientation for OCR
- **OCR Quality**: Automatic rotation significantly improves text extraction accuracy for sideways documents
- **API Endpoints**: Added `/api/rotate_document/<doc_id>` for manual rotation application
  - Reprocesses PDF with new orientation
  - Updates OCR text and confidence scores
  - Returns suggestions for AI re-analysis

### Changed
- **Document Detection Logic**: Replaced single-page sampling with strategic multi-point analysis
- **LLM Analysis Prompt**: Enhanced to handle multiple page samples and detect document boundaries
- **Processing Pipeline**: Integrated automatic rotation detection into single document workflow
- **Batch Completion**: Added cleanup step to remove empty directories after successful export

### Fixed
- **Document Detection Blind Spot**: Multi-document batch scans starting with professional documents now correctly classified
- **Sideways PDF Issue**: Single document workflow now handles rotated documents automatically and manually
- **Directory Cleanup**: Empty batch directories are now properly cleaned up after export completion
- **OCR Accuracy**: Optimal rotation detection improves text extraction quality for better AI analysis

### Developer / Infrastructure
- **Multi-Point Sampling Function**: `_detect_best_rotation()` for automatic orientation detection
- **Cleanup Functions**: `cleanup_empty_batch_directory()` and `cleanup_batch_on_completion()`
- **Enhanced Processing**: Updated `create_searchable_pdf()` with rotation detection integration
- **Safety Mechanisms**: Comprehensive directory safety checks prevent accidental deletion
- **Audit Trail**: All rotation and cleanup actions logged to interaction_log table

### UX Improvements
- **Better Document Classification**: Reduced false single-document classifications for batch scans
- **Rotation Workflow**: Familiar rotation controls borrowed from batch workflow
- **Clear Status Feedback**: Rotation status and confidence scores displayed to users
- **Automatic Processing**: Most rotation issues resolved automatically without user intervention
- **Clean Workspace**: Batch directories automatically cleaned up, reducing storage usage

## [2025-09-29] - Export Button UI Fixes & Workflow Consistency
### Added
- **Flash Message System**: Implemented comprehensive flash message display in base template with success/error/info styling
- **Export Button Visual Feedback**: Added "Processing..." state with spinner animation during export operations
- **Batch Workflow Consistency**: Extended "Revisit Batch" and "Reset Batch" functionality to exported single document batches
- **Missing CSS Classes**: Added `.btn-secondary` styling for previously invisible "Edit Again" buttons

### Changed
- **Export Button Behavior**: Removed conflicting JavaScript that prevented form submission in Simple Browser
- **Button Spacing**: Fixed large gaps between action buttons with proper inline styling
- **Flash Message Integration**: All export operations now show clear success/error feedback to users
- **Exported Batch Actions**: "Exported" status now shows same action buttons as "complete" batches (View Documents, Revisit Batch, Reset Batch)

### Fixed
- **Export Button Functionality**: Resolved issue where export button appeared to do nothing due to JavaScript conflicts
- **Invisible UI Elements**: Fixed "Edit Again" button that was present but invisible due to missing CSS styling
- **Form Submission Blocking**: Removed confirmation dialog and conflicting JavaScript that prevented form submission
- **Browser Compatibility**: Export functionality now works properly in VS Code Simple Browser environment
- **User Feedback Gap**: Export operations now provide clear visual feedback and status updates

### Developer / Infrastructure
- **Base Template Enhancement**: Added flash message handling with categorized styling (success/error/info)
- **JavaScript Cleanup**: Removed conflicting event handlers that interfered with form submission
- **CSS Standardization**: Ensured all action buttons have proper styling classes defined
- **Template Consistency**: Unified action button patterns across all batch statuses

### UX Improvements
- **Clear Export Feedback**: Users now see confirmation when export operations complete successfully
- **Consistent Button Visibility**: All action buttons are now visible and properly styled
- **Workflow Parity**: Exported single document batches have same management options as traditional batches
- **Simple Browser Support**: All functionality works correctly in VS Code's Simple Browser without external developer tools

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

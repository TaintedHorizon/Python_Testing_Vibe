#!/usr/bin/env python3
"""Structure Verification Script

Purpose:
  Verifies the repository tree against an expected set of required paths and flags:
    * Missing required files/directories
    * Unexpected legacy artifacts (that should have been removed)
    * Optional runtime directories that may be safely absent

Usage:
  Activate the virtual environment, then run:
      python dev_tools/verify_structure.py

Exit Codes:
  0 = All checks passed
  1 = Missing required items or unexpected artifacts found

Notes:
  - This script is intentionally lightweight (no external deps).
  - Update EXPECTED_FILES/EXPECTED_DIRS when adding core components.
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PROCESSOR = REPO_ROOT / 'doc_processor'

# Core required files (must exist)
EXPECTED_FILES = [
    'start_app.sh',
    'README.md',
    'ARCHITECTURE.md',
    'doc_processor/app.py',
    'doc_processor/config_manager.py',
    'doc_processor/database.py',
    'doc_processor/processing.py',
    'doc_processor/document_detector.py',
    'doc_processor/llm_utils.py',
    'doc_processor/security.py',
    'doc_processor/exceptions.py',
    'doc_processor/batch_guard.py',
    'doc_processor/utils/helpers.py',
    'doc_processor/services/document_service.py',
    'doc_processor/services/batch_service.py',
    'doc_processor/services/export_service.py',
    'doc_processor/routes/intake.py',
    'doc_processor/routes/batch.py',
    'doc_processor/routes/manipulation.py',
    'doc_processor/routes/export.py',
    'doc_processor/routes/admin.py',
    'doc_processor/routes/api.py',
    'doc_processor/templates/base.html',
    'doc_processor/templates/pdf_viewer.html',
    'doc_processor/static/pdfjs/pdf.min.js',
    'doc_processor/CHANGELOG.md',
    'doc_processor/docs/USAGE.md',
    'doc_processor/readme.md',
    'doc_processor/requirements.txt',
    '.github/copilot-instructions.md',
]

# Required directories (must exist)
EXPECTED_DIRS = [
    'doc_processor/dev_tools',
    'doc_processor/templates',
    'doc_processor/static/pdfjs',
    'doc_processor/services',
    'doc_processor/routes',
    'doc_processor/tests',
    'normalized',
]

# Optional runtime dirs (warn if missing but do not fail)
OPTIONAL_DIRS = [
    'doc_processor/intake',
    'doc_processor/processed',
    'doc_processor/filing_cabinet',
    'doc_processor/logs',
]

# Artifacts that should no longer exist
PROHIBITED = [
    'doc_processor/app_monolithic_backup.py',
    'doc_processor/app_original_backup.py',
    'doc_processor/LICENSE',
]

def check():
    missing_files = []
    missing_dirs = []
    missing_optional = []
    prohibited_present = []

    for rel in EXPECTED_FILES:
        if not (REPO_ROOT / rel).is_file():
            missing_files.append(rel)

    for rel in EXPECTED_DIRS:
        if not (REPO_ROOT / rel).is_dir():
            missing_dirs.append(rel)

    for rel in OPTIONAL_DIRS:
        if not (REPO_ROOT / rel).is_dir():
            missing_optional.append(rel)

    for rel in PROHIBITED:
        if (REPO_ROOT / rel).exists():
            prohibited_present.append(rel)

    status = 0
    if missing_files or missing_dirs or prohibited_present:
        status = 1

    print('\nStructure Verification Report')
    print('============================')
    if missing_files:
        print('\n❌ Missing required files:')
        for f in missing_files:
            print(f'  - {f}')
    else:
        print('\n✅ All required files present.')

    if missing_dirs:
        print('\n❌ Missing required directories:')
        for d in missing_dirs:
            print(f'  - {d}')
    else:
        print('\n✅ All required directories present.')

    if prohibited_present:
        print('\n⚠️ Prohibited legacy artifacts still present:')
        for p in prohibited_present:
            print(f'  - {p}')
    else:
        print('\n✅ No prohibited legacy artifacts detected.')

    if missing_optional:
        print('\nℹ️ Optional runtime dirs missing (created lazily at runtime):')
        for o in missing_optional:
            print(f'  - {o}')
    else:
        print('\n✅ Optional runtime dirs present.')

    print('\nExit Status:', status)
    return status

if __name__ == '__main__':  # pragma: no cover
    sys.exit(check())

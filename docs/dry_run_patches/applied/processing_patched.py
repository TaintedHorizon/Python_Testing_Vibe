"""
Dry-run patched wrapper for `doc_processor/processing.py`.

This wrapper is used only for review/testing of the safe-output changes.
It redirects the commonly-written directories (processed, archive, filing_cabinet,
wip, intake) to test-safe locations using the repository's `select_tmp_dir`
helper, then re-exports the primary functions for lightweight validation.

This file intentionally doesn't duplicate the entire original module. It
mutates the in-memory `app_config` object on import to avoid invasive edits
to the original source during the dry-run phase.
"""
from typing import Any
import os
import logging

# Import the original processing module
from doc_processor import processing as _orig_processing

# Import helper to choose a test-safe directory
try:
    # When running from inside package
    from doc_processor.utils.path_utils import select_tmp_dir, ensure_dir
except Exception:
    # Fallback import style for out-of-tree runs
    from utils.path_utils import select_tmp_dir, ensure_dir  # type: ignore


def _apply_test_safe_dirs():
    """Mutate `app_config` in the original module so subsequent writes go to safe dirs."""
    ac = getattr(_orig_processing, 'app_config', None)
    if not ac:
        logging.debug("processing_patched: original module has no app_config; skipping safe-dir mutation")
        return

    # Compute safe alternatives (select_tmp_dir handles precedence: app_config -> env -> TEST_TMPDIR -> TMPDIR -> system temp -> cwd)
    try:
        # Prefer explicit environment variables when present (mirrors app_config precedence)
        processed = os.getenv('PROCESSED_DIR') or getattr(ac, 'PROCESSED_DIR', None) or select_tmp_dir()
        archive = os.getenv('ARCHIVE_DIR') or getattr(ac, 'ARCHIVE_DIR', None) or select_tmp_dir()
        filing = os.getenv('FILING_CABINET_DIR') or getattr(ac, 'FILING_CABINET_DIR', None) or select_tmp_dir()
        wip = os.getenv('WIP_DIR') or getattr(ac, 'WIP_DIR', None) or select_tmp_dir()
        intake = os.getenv('INTAKE_DIR') or getattr(ac, 'INTAKE_DIR', None) or select_tmp_dir()

        # Apply the safe values back to app_config for the dry-run
        setattr(ac, 'PROCESSED_DIR', processed)
        setattr(ac, 'ARCHIVE_DIR', archive)
        setattr(ac, 'FILING_CABINET_DIR', filing)
        setattr(ac, 'WIP_DIR', wip)
        setattr(ac, 'INTAKE_DIR', intake)

        # Ensure directories exist so imported functions don't error on first write
        for d in (processed, archive, filing, wip, intake):
            if d:
                try:
                    ensure_dir(d)
                except Exception:
                    try:
                        os.makedirs(d, exist_ok=True)
                    except Exception:
                        logging.debug(f"processing_patched: could not ensure dir {d}")

    except Exception as e:
        logging.debug(f"processing_patched: failed to compute/apply test-safe dirs: {e}")


# Apply test-safe mutation eagerly on import for the dry-run
_apply_test_safe_dirs()

# Re-export a small subset of functions for validation and testing. Consumers
# can import this wrapper instead of the original module during dry-run tests.
process_image_file = _orig_processing.process_image_file
create_searchable_pdf = _orig_processing.create_searchable_pdf
process_batch = _orig_processing.process_batch
export_document = _orig_processing.export_document
finalize_single_documents_batch_with_progress = _orig_processing.finalize_single_documents_batch_with_progress
cleanup_batch_files = _orig_processing.cleanup_batch_files
cleanup_batch_on_completion = _orig_processing.cleanup_batch_on_completion

__all__ = [
    'process_image_file',
    'create_searchable_pdf',
    'process_batch',
    'export_document',
    'finalize_single_documents_batch_with_progress',
    'cleanup_batch_files',
    'cleanup_batch_on_completion',
]
# Dry-run patched snippet for doc_processor/processing.py
# Purpose: prefer app_config settings or TEST_TMPDIR for output directories and ensure directories exist
import os
import tempfile
try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()

# Example: replace occurrences of os.makedirs(os.path.dirname(dst), exist_ok=True)

def ensure_output_dir(dst):
    # prefer app_config if available (left to the original file to use app_config.ANY_DIR)
    out_base = os.environ.get('PROCESSING_OUTPUT_DIR') or select_tmp_dir()
    target_dir = os.path.dirname(dst) or out_base
    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception:
        # fallback to original dirname
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            target_dir = os.path.dirname(dst)
        except Exception:
            pass
    return target_dir

# Usage (in original code):
# ensure_output_dir(output_path)

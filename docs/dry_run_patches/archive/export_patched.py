"""
Dry-run patched wrapper for `doc_processor/routes/export.py`.

This wrapper ensures that `app_config.FILING_CABINET_DIR` and other
filesystem-facing config values are set to test-safe locations (preferring
explicit env overrides, then TEST_TMPDIR, then system tempdir) before the
original module uses them. It re-exports the `bp` Blueprint for lightweight
integration tests.
"""
import os
import logging

from doc_processor.routes import export as _orig
try:
    from doc_processor.utils.path_utils import select_tmp_dir, ensure_dir
except Exception:
    from utils.path_utils import select_tmp_dir, ensure_dir  # type: ignore


def _apply_test_safe_filing_dir():
    try:
        from doc_processor.config_manager import app_config as ac
    except Exception:
        ac = getattr(_orig, 'app_config', None)

    # Prefer explicit env var, then existing app_config value, then select_tmp_dir()
    filing = os.getenv('FILING_CABINET_DIR') or (getattr(ac, 'FILING_CABINET_DIR', None) if ac else None) or select_tmp_dir()
    try:
        ensure_dir(filing)
    except Exception:
        try:
            os.makedirs(filing, exist_ok=True)
        except Exception:
            logging.debug(f"export_patched: could not ensure filing dir {filing}")

    if ac:
        try:
            setattr(ac, 'FILING_CABINET_DIR', filing)
        except Exception:
            pass
    os.environ['FILING_CABINET_DIR'] = filing


_apply_test_safe_filing_dir()

# Re-export Blueprint and key helpers for tests to import
bp = getattr(_orig, 'bp')
export_service = getattr(_orig, 'export_service', None)
_resolve_filing_cabinet_dir = getattr(_orig, '_resolve_filing_cabinet_dir')

__all__ = ['bp', 'export_service', '_resolve_filing_cabinet_dir']

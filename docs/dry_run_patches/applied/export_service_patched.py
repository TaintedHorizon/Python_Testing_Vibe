"""
Dry-run patched wrapper for `doc_processor/services/export_service.py`.

This wrapper sets TEST-safe environment for export resolution and re-exports
the ExportService class for tests to use without modifying the original file.
"""
import os
import logging

from doc_processor.services import export_service as _orig
try:
    from doc_processor.utils.path_utils import select_tmp_dir
    # avoid depending on the exact signature of ensure_dir from the project's helper
    # provide a local, type-stable wrapper instead
    def _ensure_dir(p: str) -> None:
        from doc_processor.utils.path_utils import ensure_dir as _ed
        try:
            _ed(p)
        except Exception:
            try:
                os.makedirs(p, exist_ok=True)
            except Exception:
                pass
except Exception:
    def select_tmp_dir():
        import tempfile as _temp
        return os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or _temp.gettempdir()
    def _ensure_dir(p: str) -> None:
        try:
            os.makedirs(p, exist_ok=True)
        except Exception:
            pass


def _ensure_test_export_dir():
    # Respect explicit env override, then app_config, then test tmp
    try:
        from doc_processor.config_manager import app_config as ac
    except Exception:
        ac = getattr(_orig, 'app_config', None)

    export_env = os.getenv('EXPORT_DIR') or (getattr(ac, 'EXPORT_DIR', None) if ac else None)
    if export_env:
        export_dir = export_env
    else:
        tmp = select_tmp_dir()
        export_dir = os.path.join(tmp, 'exports')

    try:
        _ensure_dir(export_dir)
    except Exception:
        try:
            os.makedirs(export_dir, exist_ok=True)
        except Exception:
            logging.debug(f"export_service_patched: could not ensure export dir {export_dir}")

    os.environ['EXPORT_DIR'] = export_dir
    if ac:
        try:
            setattr(ac, 'EXPORT_DIR', export_dir)
        except Exception:
            pass


_ensure_test_export_dir()

# Re-export ExportService to be used by tests
ExportService = _orig.ExportService
_resolve_export_dir = _orig._resolve_export_dir

__all__ = ['ExportService', '_resolve_export_dir']

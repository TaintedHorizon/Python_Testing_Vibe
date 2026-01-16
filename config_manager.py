# Compatibility shim for top-level imports in tests and scripts.
# Exposes `app_config` from the `doc_processor` package for legacy imports like
# `from config_manager import app_config` used throughout the test suite.
try:
    from doc_processor.config_manager import app_config
except Exception:
    # Fallback to an archived or alternate location if present
    try:
        from archive.root_cleanup.config_manager import app_config
    except Exception:
        raise

"""
Compatibility shim for older imports.
Some tests and legacy code import `config_manager` as a top-level module.
Re-export the implementation from the `doc_processor` package so imports keep working.
"""

from doc_processor.config_manager import *  # noqa: F401,F403

# Optional explicit export
try:
    __all__ = doc_processor.config_manager.__all__  # type: ignore[name-defined]
except Exception:
    pass

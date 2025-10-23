"""
Dry-run wrapper for tools/gamelist_editor/gamelist_xml_editor.py

Ensures any backup or output files are written under TEST_TMPDIR/select_tmp_dir
when running tests so the repository isn't modified.
"""
from __future__ import annotations

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
os.makedirs(base, exist_ok=True)
os.environ.setdefault('GAMELIST_BACKUP_DIR', os.path.join(base, 'gamelist_backups'))
os.environ.setdefault('GAMELIST_OUTPUT_DIR', os.path.join(base, 'gamelist_out'))

from tools.gamelist_editor.gamelist_xml_editor import main, GamelistEditor  # type: ignore

__all__ = ['main', 'GamelistEditor']
# Dry-run patched copy of tools/gamelist_editor/gamelist_xml_editor.py
# Purpose: use GAMELIST_OUTPUT_DIR -> select_tmp_dir() -> gamelist_dir and ensure directory exists.

import os
import tempfile
try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        return os.environ.get('GAMELIST_BACKUP_DIR') or os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()

# (rest of the module is elided in this dry-run copy; only the output path resolution is shown)

def write_new_gamelist(tree, gamelist_dir):
    # Prefer explicit env var, then select_tmp_dir (which prefers TEST_TMPDIR), then gamelist_dir as last resort
    safe_output_base = os.environ.get('GAMELIST_OUTPUT_DIR') or select_tmp_dir() or gamelist_dir
    try:
        os.makedirs(safe_output_base, exist_ok=True)
    except Exception:
        # best-effort: fallback to gamelist_dir
        safe_output_base = gamelist_dir

    new_gamelist_output_path = os.path.join(safe_output_base, "gamelist_new.xml")
    # Example write (would be tree.write in real file)
    with open(new_gamelist_output_path, 'w', encoding='utf-8') as f:
        f.write("<!-- dry-run patched output -->")

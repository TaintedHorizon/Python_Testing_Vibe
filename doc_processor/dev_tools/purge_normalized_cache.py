#!/usr/bin/env python3
"""Purge normalized PDF cache.

Removes all files in the configured NORMALIZED_DIR (image->PDF normalization cache).
Safe to run anytime; rebuilt lazily. Honors configuration via config_manager.
"""
from __future__ import annotations
import os, sys, shutil
from pathlib import Path

try:
    from config_manager import app_config
except ImportError:  # pragma: no cover
    print("❌ Unable to import config_manager. Run from repo root.")
    sys.exit(1)

def main():
    norm = Path(app_config.NORMALIZED_DIR)
    if not norm.exists():
        print(f"✅ No cache directory exists: {norm}")
        return 0
    if not norm.is_dir():
        print(f"❌ NORMALIZED_DIR is not a directory: {norm}")
        return 2
    entries = list(norm.iterdir())
    if not entries:
        print(f"✅ Cache already empty: {norm}")
        return 0
    removed = 0
    for p in entries:
        try:
            if p.is_file():
                p.unlink()
                removed += 1
        except Exception as e:
            print(f"⚠️ Failed to remove {p}: {e}")
    print(f"🧹 Purged {removed} normalized file(s) from {norm}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
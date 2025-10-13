#!/usr/bin/env python3
"""
Strip trailing whitespace and remove spaces on blank lines for Python files under repo directories.
Safe, idempotent, and limited to .py files.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ["doc_processor", "tools", "tests", "scripts", ""]

def normalize_file(p: Path) -> bool:
    try:
        text = p.read_text(encoding='utf-8')
    except Exception:
        return False
    changed = False
    lines = text.splitlines()
    new_lines = []
    for line in lines:
        # remove trailing whitespace
        stripped = line.rstrip()
        # if the line becomes empty, keep exactly '' (no spaces)
        if stripped == '' and line != '':
            changed = True
            new_lines.append('')
        else:
            if stripped != line:
                changed = True
            new_lines.append(stripped)
    if changed:
        p.write_text('\n'.join(new_lines) + ('\n' if text.endswith('\n') else ''), encoding='utf-8')
    return changed

if __name__ == '__main__':
    files = []
    for pattern in PATTERNS:
        base = ROOT / pattern if pattern else ROOT
        for p in base.rglob('*.py'):
            # skip virtualenvs and __pycache__
            if 'venv' in p.parts or '__pycache__' in p.parts:
                continue
            files.append(p)
    modified = 0
    for f in files:
        if normalize_file(f):
            print(f"Normalized: {f}")
            modified += 1
    print(f"Total files modified: {modified}")
    sys.exit(0)

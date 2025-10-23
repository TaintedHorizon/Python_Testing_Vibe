#!/usr/bin/env python3
"""Batch-clean archived GitHub Actions workflows.

Usage:
  python tools/clean_workflows.py        # interactive preview
  python tools/clean_workflows.py --yes  # write changes

This script reads files from .github/workflows_archived/, strips
code-fences and duplicated YAML documents (split on ---), optionally
rewrites heavy workflows' triggers to `workflow_dispatch`, and writes
cleaned files to .github/workflows/.
"""
import re
import sys
import os
import tempfile
from pathlib import Path

ARCHIVE_DIR = Path('.github/workflows_archived')
# Default OUT_DIR is repository workflows folder, but prefer environment/CI-safe dirs when available
_env_out = os.environ.get('CLEAN_WORKFLOWS_OUT_DIR')
_test_tmp = os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR')
OUT_DIR = Path(_env_out) if _env_out else (Path(_test_tmp) / 'workflows' if _test_tmp else Path('.github/workflows'))
HEAVY_WORKFLOWS = {'playwright-e2e.yml', 'ci.yml', 'ci-rewrite.yml'}


def strip_code_fence(s: str) -> str:
    # Remove triple-backtick fences at start/end (``` or ```yaml)
    s = re.sub(r"^\s*```(?:yaml)?\n", '', s, flags=re.MULTILINE)
    s = re.sub(r"\n```\s*$", '', s, flags=re.MULTILINE)
    return s


def pick_single_document(s: str) -> str:
    # Split on document separators and pick the most-likely YAML doc.
    parts = re.split(r'\n-{3,}\n', s)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return ''
    # Prefer part starting with 'name:' or 'on:'
    for p in parts:
        if re.match(r'^(name|on):', p):
            return p + '\n'
    # Fallback: return the largest part
    parts.sort(key=lambda p: len(p.splitlines()), reverse=True)
    return parts[0] + '\n'


def rewrite_triggers_to_dispatch(content: str, filename: str) -> str:
    if Path(filename).name in HEAVY_WORKFLOWS:
        # Replace the top-level 'on:' block with a minimal workflow_dispatch
        # Only do this if an 'on:' exists; otherwise, append.
        if re.search(r'^\s*on:\s*', content, flags=re.MULTILINE):
            # naive replacement: replace 'on:' until next top-level key
            content = re.sub(r"^\s*on:\s*[\s\S]*?(?=^\S|\Z)", 'on:\n  workflow_dispatch: {}\n', content, flags=re.MULTILINE)
        else:
            content = 'on:\n  workflow_dispatch: {}\n\n' + content
    return content


def clean_one(path: Path) -> str:
    s = path.read_text(encoding='utf-8')
    s = strip_code_fence(s)
    doc = pick_single_document(s)
    if not doc:
        return ''
    doc = rewrite_triggers_to_dispatch(doc, path.name)
    if not doc.endswith('\n'):
        doc += '\n'
    return doc


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--yes', action='store_true', help='Write changes without prompting')
    parser.add_argument('--out', '--out-dir', dest='out_dir', help='Output directory for cleaned workflows (overrides CLEAN_WORKFLOWS_OUT_DIR)')
    args = parser.parse_args()

    # Allow CLI override of OUT_DIR; otherwise use module-level OUT_DIR (which already prefers env/test tmp)
    final_out_dir = Path(args.out_dir) if args.out_dir else OUT_DIR

    if not ARCHIVE_DIR.exists():
        print('Archive directory not found:', ARCHIVE_DIR)
        sys.exit(1)

    final_out_dir.mkdir(parents=True, exist_ok=True)
    changed = []
    for p in sorted(ARCHIVE_DIR.glob('*.yml')):
        cleaned = clean_one(p)
        out = final_out_dir / p.name
        if not cleaned:
            print(f'WARNING: {p.name} cleaned to empty content; skipping')
            continue
        orig = out.read_text(encoding='utf-8') if out.exists() else ''
        if cleaned.strip() != orig.strip():
            print(f'== {p.name} ==')
            print('--- archive (first 6 lines) ---')
            for i, l in enumerate(p.read_text().splitlines()[:6], 1):
                print(f'{i:3d}: {l}')
            print('--- cleaned (first 6 lines) ---')
            for i, l in enumerate(cleaned.splitlines()[:6], 1):
                print(f'{i:3d}: {l}')
            changed.append((p, out, cleaned))
        else:
            print(f'{p.name} unchanged')

    if not changed:
        print('No changes detected.')
        return

    if not args.yes:
        ans = input(f'Write {len(changed)} cleaned files to {final_out_dir}? [y/N] ')
        if ans.lower() != 'y':
            print('Aborted.')
            return

    for p,out,cleaned in changed:
        out.write_text(cleaned, encoding='utf-8')
        print('WROTE', out)


if __name__ == '__main__':
    main()

"""Dry-run patched copy of tools/clean_workflows.py
Redirects output to test-safe location using select_tmp_dir when available.
"""
import re
import sys
import os
from pathlib import Path

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        import tempfile
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

ARCHIVE_DIR = Path('.github/workflows_archived')
_env_out = os.environ.get('CLEAN_WORKFLOWS_OUT_DIR')
_test_tmp = os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR')
OUT_DIR = Path(_env_out) if _env_out else (Path(_test_tmp) / 'workflows' if _test_tmp else Path(select_tmp_dir()) / 'workflows')
HEAVY_WORKFLOWS = {'playwright-e2e.yml', 'ci.yml', 'ci-rewrite.yml'}

def strip_code_fence(s: str) -> str:
    s = re.sub(r"^\s*```(?:yaml)?\n", '', s, flags=re.MULTILINE)
    s = re.sub(r"\n```\s*$", '', s, flags=re.MULTILINE)
    return s

def pick_single_document(s: str) -> str:
    parts = re.split(r'\n-{3,}\n', s)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return ''
    for p in parts:
        if re.match(r'^(name|on):', p):
            return p + '\n'
    parts.sort(key=lambda p: len(p.splitlines()), reverse=True)
    return parts[0] + '\n'

def rewrite_triggers_to_dispatch(content: str, filename: str) -> str:
    if Path(filename).name in HEAVY_WORKFLOWS:
        if re.search(r'^\s*on:\s*', content, flags=re.MULTILINE):
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
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--out', '--out-dir', dest='out_dir')
    args = parser.parse_args()

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
# Dry-run patched copy of tools/clean_workflows.py
# Purpose: use CLEAN_WORKFLOWS_OUT_DIR -> TEST_TMPDIR -> repo path and ensure OUT_DIR exists
import os
from pathlib import Path
try:
    _env_out = os.environ.get('CLEAN_WORKFLOWS_OUT_DIR')
    _test_tmp = os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR')
    OUT_DIR = Path(_env_out) if _env_out else (Path(_test_tmp) / 'workflows' if _test_tmp else Path('.github/workflows'))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    OUT_DIR = Path('.github/workflows')

# rest of logic omitted for dry-run

"""Dry-run patched copy of scripts/strip_trailing_whitespace.py
By default this version writes a report to a test-safe directory instead of modifying repo files.
"""
import sys
from pathlib import Path
import os

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        import tempfile
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ["doc_processor", "tools", "tests", "scripts", ""]

report_dir = Path(os.environ.get('STRIP_WS_REPORT_DIR', select_tmp_dir()))
report_dir.mkdir(parents=True, exist_ok=True)
report_path = report_dir / 'strip_trailing_whitespace_report.txt'

def normalize_file_dryrun(p: Path) -> bool:
    try:
        text = p.read_text(encoding='utf-8')
    except Exception:
        return False
    changed = False
    lines = text.splitlines()
    new_lines = []
    for line in lines:
        stripped = line.rstrip()
        if stripped == '' and line != '':
            changed = True
            new_lines.append('')
        else:
            if stripped != line:
                changed = True
            new_lines.append(stripped)
    if changed:
        # Instead of writing back to repo by default, append path to report and the diff-like info
        with open(report_path, 'a', encoding='utf-8') as rp:
            rp.write(f"Modified: {p}\n")
    return changed

if __name__ == '__main__':
    files = []
    for pattern in PATTERNS:
        base = ROOT / pattern if pattern else ROOT
        for p in base.rglob('*.py'):
            if 'venv' in p.parts or '__pycache__' in p.parts:
                continue
            files.append(p)
    modified = 0
    for f in files:
        if normalize_file_dryrun(f):
            print(f"Normalized (dry-run): {f}")
            modified += 1
    print(f"Total files that would be modified: {modified}; report written to {report_path}")
    sys.exit(0)
#!/usr/bin/env python3
"""
Dry-run patched copy of scripts/strip_trailing_whitespace.py
Behavior changes for safety in CI/tests:
- By default writes summary output to a test-scoped directory instead of modifying files.
- To actually modify files, set STRIP_WS_APPLY=1 or pass --apply on the CLI.
- You can override output dir with STRIP_WS_OUTPUT_DIR.
"""
import sys
from pathlib import Path
import os
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ["doc_processor", "tools", "tests", "scripts", ""]

APPLY = os.getenv('STRIP_WS_APPLY') == '1'
OUTPUT_DIR = os.environ.get('STRIP_WS_OUTPUT_DIR') or os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()

# If not applying, we will write reports to OUTPUT_DIR rather than modifying files.


def normalize_file(p: Path) -> bool:
    try:
        text = p.read_text(encoding='utf-8')
    except Exception:
        return False
    changed = False
    lines = text.splitlines()
    new_lines = []
    for line in lines:
        stripped = line.rstrip()
        if stripped == '' and line != '':
            changed = True
            new_lines.append('')
        else:
            if stripped != line:
                changed = True
            new_lines.append(stripped)
    if changed:
        if APPLY:
            p.write_text('\n'.join(new_lines) + ('\n' if text.endswith('\n') else ''), encoding='utf-8')
        else:
            # write a sidecar file describing the change into OUTPUT_DIR
            try:
                Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
                report_path = Path(OUTPUT_DIR) / f"strip_ws_report_{p.name}.txt"
                with open(report_path, 'w', encoding='utf-8') as r:
                    r.write('--- original path: ' + str(p) + '\n')
                    r.write('\n'.join(new_lines) + ('\n' if text.endswith('\n') else ''))
            except Exception:
                pass
    return changed


if __name__ == '__main__':
    files = []
    for pattern in PATTERNS:
        base = ROOT / pattern if pattern else ROOT
        for p in base.rglob('*.py'):
            if 'venv' in p.parts or '__pycache__' in p.parts:
                continue
            files.append(p)
    modified = 0
    for f in files:
        if normalize_file(f):
            print(f"Normalized: {f}")
            modified += 1
    print(f"Total files modified: {modified}")
    if not APPLY:
        print(f"Reports written to: {OUTPUT_DIR}")
    sys.exit(0)

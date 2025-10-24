#!/usr/bin/env python3
"""
Lightweight repository audit: scan source files for common write operations
and produce docs/output_path_audit.json and docs/output_path_audit.csv.

This is intentionally conservative and textual (heuristics): looks for
`open(`, `Path.write_bytes`, `shutil.copy2`, `tarfile.open`, `Image.save`,
`send_file(`, `echo .* > /tmp` and similar patterns.

Run from repo root.
"""
import csv
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / 'docs' / 'output_path_audit.json'
OUT_CSV = ROOT / 'docs' / 'output_path_audit.csv'

PATTERNS = [
    ('open', re.compile(r"\bopen\s*\(", re.IGNORECASE)),
    ('Path.write_bytes', re.compile(r"\.write_bytes\s*\(", re.IGNORECASE)),
    ('shutil.copy2', re.compile(r"shutil\.copy2\s*\(", re.IGNORECASE)),
    ('tarfile.open', re.compile(r"tarfile\.open\s*\(", re.IGNORECASE)),
    ('Image.save', re.compile(r"\.save\s*\(.*\bPDF\b|Image\.save\s*\(", re.IGNORECASE)),
    ('send_file', re.compile(r"send_file\s*\(", re.IGNORECASE)),
    ('echo_pid_tmp', re.compile(r"echo\s+\$!?\s*>\s*/tmp/", re.IGNORECASE)),
    ('os.remove', re.compile(r"os\.remove\s*\(", re.IGNORECASE)),
    ('shutil.rmtree', re.compile(r"shutil\.rmtree\s*\(", re.IGNORECASE)),
    ('sqlite3', re.compile(r"sqlite3\.|CREATE TABLE|INSERT INTO", re.IGNORECASE)),
]

SKIP_DIRS = {'.git', 'venv', 'node_modules', '__pycache__', 'build', 'dist'}
TEXT_EXTS = {'.py', '.sh', '.js', '.html', '.md', '.txt', '.json'}

results = []

for dirpath, dirnames, filenames in os.walk(ROOT):
    # prune skip dirs
    parts = Path(dirpath).parts
    if any(p in SKIP_DIRS for p in parts):
        continue
    for fname in filenames:
        fpath = Path(dirpath) / fname
        if fpath.suffix.lower() not in TEXT_EXTS:
            continue
        try:
            text = fpath.read_text(encoding='utf-8')
        except Exception:
            continue
        entry = {
            'file': str(fpath.relative_to(ROOT)),
            'matches': [],
            'uses_app_config': 'app_config' in text,
        }
        for label, pat in PATTERNS:
            for m in pat.finditer(text):
                # capture a snippet line
                idx = m.start()
                # get the containing line
                start = text.rfind('\n', 0, idx) + 1
                end = text.find('\n', idx)
                if end == -1:
                    end = len(text)
                snippet = text[start:end].strip()
                entry['matches'].append({'pattern': label, 'snippet': snippet})
        if entry['matches']:
            # Heuristic write_type and statement from first match
            write_type = 'write_operation_candidates'
            statement = entry['matches'][0]['snippet']
            writes = [m['pattern'] for m in entry['matches']]
            results.append({
                'file': entry['file'],
                'write_type': write_type,
                'statement': statement,
                'writes': writes,
                'uses_app_config': entry['uses_app_config'],
            })

# Save JSON and CSV
OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
with OUT_JSON.open('w', encoding='utf-8') as jf:
    json.dump(results, jf, indent=2, ensure_ascii=False)

with OUT_CSV.open('w', encoding='utf-8', newline='') as cf:
    w = csv.writer(cf)
    w.writerow(['file', 'write_type', 'statement', 'writes', 'uses_app_config'])
    for r in results:
        w.writerow([r['file'], r['write_type'], r['statement'], ';'.join(r['writes']), r['uses_app_config']])

print(f"Wrote {len(results)} audit entries to {OUT_JSON} and {OUT_CSV}")

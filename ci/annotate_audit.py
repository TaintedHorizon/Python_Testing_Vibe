#!/usr/bin/env python3
"""
Annotate docs/output_path_audit.json entries that are test/static so they include
"status": "skipped/test/static". Also regenerate CSV to include the status column.

Run from repo root.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_P = ROOT / 'docs' / 'output_path_audit.json'
CSV_P = ROOT / 'docs' / 'output_path_audit.csv'

if not JSON_P.exists():
    print(f"Audit JSON not found at {JSON_P}")
    raise SystemExit(1)

with JSON_P.open('r', encoding='utf-8') as f:
    data = json.load(f)

# Define match heuristics for test/static entries
def is_test_or_static(entry):
    p = entry.get('file', '')
    if p.startswith('doc_processor/tests'):
        return True
    if p.startswith('doc_processor/static/pdfjs'):
        return True
    if p.startswith('doc_processor/tests/e2e'):
        return True
    # also consider artifacts dir under tests/e2e
    if 'tests/e2e/artifacts' in p:
        return True
    return False

modified = 0
for e in data:
    if is_test_or_static(e):
        if e.get('status') != 'skipped/test/static':
            e['status'] = 'skipped/test/static'
            modified += 1

if modified:
    JSON_P.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Annotated {modified} entries in {JSON_P}")
else:
    print("No entries needed annotation")

# Update CSV: create a CSV with a status column if present
import csv

def write_csv(data, path):
    with path.open('w', encoding='utf-8', newline='') as cf:
        w = csv.writer(cf)
        header = ['file', 'write_type', 'statement', 'writes', 'uses_app_config', 'status']
        w.writerow(header)
        for r in data:
            file = r.get('file','')
            write_type = r.get('write_type','')
            statement = r.get('statement','')
            writes = ';'.join(r.get('writes',[])) if isinstance(r.get('writes',[]), list) else r.get('writes','')
            uses_app_config = r.get('uses_app_config', False)
            status = r.get('status','')
            w.writerow([file, write_type, statement, writes, uses_app_config, status])

write_csv(data, CSV_P)
print(f"Wrote CSV to {CSV_P}")

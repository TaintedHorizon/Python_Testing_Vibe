"""Scan for potential SQLite database files related to the document processor.

Usage (activate venv first):
    python doc_processor/dev_tools/find_databases.py [--search-up 1] [--max-depth 4]

Outputs a table of discovered *.db files, size, mtime, and quick row counts for key tables
(batches, single_documents, documents) when present.

Safety: Read-only; never mutates files.
"""
from __future__ import annotations
import os, sys, argparse, sqlite3, time
from pathlib import Path

KEY_TABLES = ["batches", "single_documents", "documents"]

def gather_db_info(path: Path) -> dict:
    info = {
        'path': str(path),
        'size': path.stat().st_size if path.exists() else 0,
        'mtime': time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(path.stat().st_mtime)) if path.exists() else None,
        'counts': {},
        'error': None,
    }
    try:
        # If this is the active app DB, prefer the app helper which applies PRAGMAs.
        try:
            from config_manager import app_config
            if os.path.abspath(str(path)) == os.path.abspath(app_config.DATABASE_PATH):
                from ..database import get_db_connection
                conn = get_db_connection()
            else:
                # Open read-only to avoid accidental writes
                conn = sqlite3.connect(f'file:{str(path)}?mode=ro', uri=True, timeout=5.0)
        except Exception:
            conn = sqlite3.connect(f'file:{str(path)}?mode=ro', uri=True, timeout=5.0)
        assert conn is not None
        cur = conn.cursor()
        tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in KEY_TABLES:
            if t in tables:
                try:
                    info['counts'][t] = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                except Exception:
                    info['counts'][t] = 'err'
        conn.close()
    except Exception as e:
        info['error'] = str(e)
    return info

def scan(start: Path, max_depth: int) -> list[dict]:
    results = []
    for root, dirs, files in os.walk(start):
        depth = len(Path(root).relative_to(start).parts)
        if depth > max_depth:
            dirs[:] = []  # prune
            continue
        for f in files:
            if f.endswith('.db'):
                full = Path(root)/f
                results.append(gather_db_info(full))
    return sorted(results, key=lambda r: r['path'])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--search-up', type=int, default=0, help='How many parent directory levels upward to also scan')
    ap.add_argument('--max-depth', type=int, default=4, help='Max directory depth to recurse')
    args = ap.parse_args()

    roots = [Path.cwd()]
    cur = Path.cwd()
    for _ in range(args.search_up):
        cur = cur.parent
        roots.append(cur)

    all_infos = []
    for r in roots:
        all_infos.extend(scan(r, args.max_depth))

    if not all_infos:
        print('No .db files found.')
        return 0

    # Print table
    header = f"{'PATH':60}  {'SIZE':>10}  {'MTIME':19}  Batches  SingleDocs  GroupDocs  Error"
    print(header)
    print('-'*len(header))
    for info in all_infos:
        batches = info['counts'].get('batches','-')
        singles = info['counts'].get('single_documents','-')
        groups = info['counts'].get('documents','-')
        print(f"{info['path'][:60]:60}  {info['size']:10}  {info['mtime'] or '-':19}  {batches!s:7}  {singles!s:10}  {groups!s:9}  {info['error'] or ''}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

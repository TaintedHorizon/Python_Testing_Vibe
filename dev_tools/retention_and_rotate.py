#!/usr/bin/env python3
"""
dev_tools/retention_and_rotate.py

Simple retention and rotation tool for DB backups and app logs.

Features:
- Operates in dry-run mode by default; requires --confirm to perform destructive actions.
- For `DB_BACKUP_DIR` it can compress uncompressed collected backup directories into tar.gz files and
  delete backups older than a configurable number of days or keep only the newest N archives.
- For `doc_processor/logs` it can compress rotated logs and delete older compressed logs beyond retention.

Usage examples:
  # Dry-run report
  ./dev_tools/retention_and_rotate.py

  # Compress uncompressed backup dirs, keep 5 newest, delete older than 90 days
  ./dev_tools/retention_and_rotate.py --compress-backups --keep 5 --delete-older-than 90 --confirm

This tool is intentionally conservative and prints planned actions unless --confirm is passed.
"""
from __future__ import annotations
import argparse
import datetime
import shutil
import tarfile
from pathlib import Path
import os
import sys
import tempfile


def load_env():
    env = {}
    # Prefer explicit env var; then prefer TEST_TMPDIR/TMPDIR when present to make CI/test runs safe,
    # otherwise fall back to system tempdir to avoid operating inside the repo by default.
    # Allow app_config to override when running from the processor context
    try:
        from doc_processor.config_manager import app_config
        app_db_backup = getattr(app_config, 'DB_BACKUP_DIR', None)
    except Exception:
        app_db_backup = None

    env['DB_BACKUP_DIR'] = (
        os.environ.get('DB_BACKUP_DIR')
        or app_db_backup
        or os.environ.get('TEST_TMPDIR')
        or os.environ.get('TMPDIR')
        or tempfile.gettempdir()
    )

    # Default logs path is inside the repo. However, when TEST_TMPDIR is set (tests/CI), prefer
    # using that to keep test artifacts out of the repo. If LOG_FILE_PATH is explicitly set, honor it.
    repo_root = Path(__file__).resolve().parents[1]
    explicit_log = os.environ.get('LOG_FILE_PATH')
    try:
        app_log_dir = getattr(app_config, 'LOG_FILE_PATH', None)
    except Exception:
        app_log_dir = None

    if explicit_log:
        env['LOG_DIR'] = explicit_log
    elif app_log_dir:
        env['LOG_DIR'] = app_log_dir
    elif os.environ.get('TEST_TMPDIR'):
        _tmp = os.environ['TEST_TMPDIR']
        env['LOG_DIR'] = os.path.join(_tmp, 'logs')
    else:
        env['LOG_DIR'] = str(repo_root / 'doc_processor' / 'logs')
    # Best-effort: create these directories when possible so CI/tests have places to write
    try:
        dbd = Path(env['DB_BACKUP_DIR'])
        dbd.mkdir(parents=True, exist_ok=True)
    except Exception:
        try:
            env['DB_BACKUP_DIR'] = tempfile.gettempdir()
            Path(env['DB_BACKUP_DIR']).mkdir(parents=True, exist_ok=True)
        except Exception:
            env['DB_BACKUP_DIR'] = os.getcwd()

    try:
        logd = Path(env['LOG_DIR'])
        # If LOG_DIR looks like a file path, ensure parent exists
        if logd.suffix:
            logd.parent.mkdir(parents=True, exist_ok=True)
        else:
            logd.mkdir(parents=True, exist_ok=True)
    except Exception:
        try:
            env['LOG_DIR'] = tempfile.gettempdir()
            Path(env['LOG_DIR']).mkdir(parents=True, exist_ok=True)
        except Exception:
            env['LOG_DIR'] = os.getcwd()
    return env


def find_backups(backup_dir: Path):
    if not backup_dir.exists():
        return []
    # consider both tar.gz files and collected_backup_* directories
    items = []
    for p in backup_dir.iterdir():
        if p.name.startswith('collected_backup_') or p.suffix in ('.gz', '.tgz', '.tar', '.zip'):
            items.append(p)
    # sort by mtime desc
    items.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return items


def compress_dir(src: Path, dry_run: bool=True):
    dest = src.with_suffix('.tar.gz')
    if dry_run:
        return f'COMPRESS {src} -> {dest}'
    # create tar.gz
    with tarfile.open(dest, 'w:gz') as tar:
        tar.add(str(src), arcname=src.name)
    # remove original dir
    shutil.rmtree(src)
    return f'COMPRESSED {src} -> {dest}'


def delete_path(p: Path, dry_run: bool=True):
    if dry_run:
        return f'DELETE {p}'
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    return f'DELETED {p}'


def rotate_logs(log_dir: Path, keep: int=5, dry_run: bool=True):
    actions = []
    if not log_dir.exists():
        return actions
    # target compressed logs: *.gz
    gz = sorted([p for p in log_dir.iterdir() if p.suffix == '.gz'], key=lambda x: x.stat().st_mtime, reverse=True)
    # delete gz older than keep
    for p in gz[keep:]:
        actions.append(delete_path(p, dry_run=dry_run))
    return actions


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='Retention and rotation tool (dry-run by default).')
    p.add_argument('--compress-backups', action='store_true', help='Compress uncompressed collected_backup_* dirs into tar.gz')
    p.add_argument('--keep', type=int, default=5, help='Number of newest backup archives to keep')
    p.add_argument('--delete-older-than', type=int, default=None, help='Delete backups older than DAYS')
    p.add_argument('--rotate-logs', action='store_true', help='Rotate/delete older compressed logs in logs dir')
    p.add_argument('--confirm', action='store_true', help='Perform actions (default is dry-run)')
    args = p.parse_args(argv)

    env = load_env()
    backup_dir = Path(env['DB_BACKUP_DIR'])
    log_dir = Path(env['LOG_DIR']).parent if Path(env['LOG_DIR']).is_file() else Path(env['LOG_DIR'])

    dry_run = not args.confirm
    actions = []

    backups = find_backups(backup_dir)
    # compress uncompressed dirs
    if args.compress_backups:
        for b in backups:
            if b.is_dir() and not any(str(b).endswith(s) for s in ('.tar.gz','.tgz')):
                actions.append(compress_dir(b, dry_run=dry_run))

    # refresh list
    backups = find_backups(backup_dir)
    # delete by keep
    if len(backups) > args.keep:
        for old in backups[args.keep:]:
            actions.append(delete_path(old, dry_run=dry_run))

    # delete by age
    if args.delete_older_than is not None:
        cutoff = datetime.datetime.now().timestamp() - (args.delete_older_than * 86400)
        for b in backups:
            try:
                if b.stat().st_mtime < cutoff:
                    actions.append(delete_path(b, dry_run=dry_run))
            except Exception:
                pass

    # rotate logs
    if args.rotate_logs:
        actions.extend(rotate_logs(log_dir, keep=args.keep, dry_run=dry_run))

    # print actions
    print('DRY-RUN' if dry_run else 'EXECUTE')
    print('Backup dir:', backup_dir)
    print('Log dir:', log_dir)
    print('Planned actions:')
    for a in actions:
        print('  ', a)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())

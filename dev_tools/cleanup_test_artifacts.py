#!/usr/bin/env python3
"""
dev_tools/cleanup_test_artifacts.py

Safe cleanup tool for test artifacts and repo-local backups.

Features:
- Dry-run by default (no destructive actions).
- --confirm to perform moves (destructive). When confirmed, files are moved into DB_BACKUP_DIR/<timestamp>/
- Safety checks: will only operate on paths that are within allowed bases read from environment or common repo paths.
- --tar to create a tar.gz of the collected backup and keep it in DB_BACKUP_DIR.
- --allow-tmp to allow cleaning /tmp/pytest-of-svc-scan* dirs.

Usage examples:
  # Dry-run (default): show what would be done
  ./dev_tools/cleanup_test_artifacts.py

  # Perform the move and create a tarball
  ./dev_tools/cleanup_test_artifacts.py --confirm --tar

This script is intentionally conservative. It will refuse to delete or move files
outside of discovered allowed base directories unless --force is passed.
"""
from __future__ import annotations
import argparse
import datetime
import shutil
import tarfile
from pathlib import Path
import os
import tempfile
import sys


def load_env_paths() -> dict:
    # Prefer environment variables; if a .env loader is present, the environment
    # will already be populated by how the repo runs. Fall back to common repo
    # locations.
    keys = dict(
        INTAKE_DIR=os.environ.get('INTAKE_DIR'),
        PROCESSED_DIR=os.environ.get('PROCESSED_DIR'),
        ARCHIVE_DIR=os.environ.get('ARCHIVE_DIR'),
        FILING_CABINET_DIR=os.environ.get('FILING_CABINET_DIR'),
        NORMALIZED_DIR=os.environ.get('NORMALIZED_DIR'),
        DB_BACKUP_DIR=os.environ.get('DB_BACKUP_DIR'),
        DATABASE_PATH=os.environ.get('DATABASE_PATH'),
    )
    # sensible repo-local defaults (do not overwrite if env provided)
    repo_root = Path(__file__).resolve().parents[1]
    if not keys['DB_BACKUP_DIR']:
        keys['DB_BACKUP_DIR'] = str(repo_root / 'db_backups')
    return keys


def _select_tmp_dir() -> str:
    """Select a temporary directory: TEST_TMPDIR -> TMPDIR -> system tempdir -> cwd."""
    try:
        import tempfile
        return os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()
    except Exception:
        return os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or os.getcwd()


def find_candidates(env_paths: dict, allow_tmp: bool=False) -> list[Path]:
    candidates = []
    # repo-local backup folders
    repo_root = Path(__file__).resolve().parents[1]
    repo_db_prod = repo_root / 'db_prod_backups'
    repo_db_backups = repo_root / 'db_backups'
    for p in (repo_db_prod, repo_db_backups):
        if p.exists():
            candidates.append(p)

    # env configured locations
    for key in ('INTAKE_DIR','PROCESSED_DIR','ARCHIVE_DIR','FILING_CABINET_DIR','NORMALIZED_DIR'):
        val = env_paths.get(key)
        if val:
            p = Path(val)
            if p.exists():
                candidates.append(p)

    # database file (suspect zero-byte file)
    dbp = env_paths.get('DATABASE_PATH')
    if dbp:
        p = Path(dbp)
        if p.exists():
            candidates.append(p)

    # canonical backup dir
    db_backup_dir_val = env_paths.get('DB_BACKUP_DIR') or str(repo_root / 'db_backups')
    db_backup_dir = Path(db_backup_dir_val)
    if db_backup_dir.exists():
        # include its contents so we can archive them in one place if needed
        candidates.append(db_backup_dir)

    # optional tmp pytest dirs
    if allow_tmp:
        import glob
        tmpdir = _select_tmp_dir()
        pattern = os.path.join(tmpdir, 'pytest-of-*')
        for p in glob.glob(pattern):
            candidates.append(Path(p))

    # dedupe and return
    seen = []
    out = []
    for p in candidates:
        rp = p.resolve()
        if rp not in seen:
            seen.append(rp)
            out.append(rp)
    return out


def is_within_allowed(path: Path, allowed_bases: list[Path]) -> bool:
    try:
        for base in allowed_bases:
            try:
                if path.resolve().is_relative_to(base.resolve()):
                    return True
            except Exception:
                # older Python versions may not have is_relative_to
                try:
                    path.resolve().relative_to(base.resolve())
                    return True
                except Exception:
                    pass
        return False
    except Exception:
        return False


def copy_or_move(src: Path, dst_root: Path, *, do_move: bool=False, dry_run: bool=True):
    """Copy (dry-run) or move (confirm) src into dst_root preserving relative layout."""
    dst_root.mkdir(parents=True, exist_ok=True)
    actions = []
    if src.is_file():
        rel = src.name
        dst = dst_root / rel
        if dry_run:
            actions.append(f'COPY {src} -> {dst}')
        else:
            if do_move:
                shutil.move(str(src), str(dst))
                actions.append(f'MOVED {src} -> {dst}')
            else:
                shutil.copy2(str(src), str(dst))
                actions.append(f'COPIED {src} -> {dst}')
    elif src.is_dir():
        # preserve the directory name under dst_root
        dst_dir = dst_root / src.name
        if dry_run:
            actions.append(f'COPYTREE {src} -> {dst_dir}')
        else:
            if do_move:
                shutil.move(str(src), str(dst_dir))
                actions.append(f'MOVED TREE {src} -> {dst_dir}')
            else:
                shutil.copytree(str(src), str(dst_dir), dirs_exist_ok=True)
                actions.append(f'COPIED TREE {src} -> {dst_dir}')
    else:
        actions.append(f'SKIP (not found) {src}')
    return actions


def create_tarball(src_dir: Path, target_tar: Path) -> None:
    with tarfile.open(target_tar, 'w:gz') as tar:
        tar.add(str(src_dir), arcname=src_dir.name)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='Safe cleanup for test artifacts (dry-run default).')
    p.add_argument('--confirm', action='store_true', help='Perform moves (destructive). Default is dry-run (no moves).')
    p.add_argument('--tar', action='store_true', help='Create tar.gz of the collected backup in DB_BACKUP_DIR.')
    p.add_argument('--allow-tmp', action='store_true', help='Allow including temporary pytest dirs for cleanup (resolved via TEST_TMPDIR/TMPDIR/system tmpdir).')
    p.add_argument('--force', action='store_true', help='Force operations on paths outside allowed bases (use with care).')
    p.add_argument('--dest', type=str, default=None, help='Optional destination backup dir (overrides env DB_BACKUP_DIR).')
    p.add_argument('--list', action='store_true', help='List discovered candidate paths and exit.')
    args = p.parse_args(argv)

    env_paths = load_env_paths()
    repo_root = Path(__file__).resolve().parents[1]
    dest_root_val = args.dest if args.dest else env_paths.get('DB_BACKUP_DIR') or str(repo_root / 'db_backups')
    dest_root = Path(str(dest_root_val))
    if not dest_root.exists():
        try:
            dest_root.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print('ERROR: cannot create dest DB_BACKUP_DIR:', dest_root, e)
            return 2

    timestamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    collected = dest_root / f'collected_backup_{timestamp}'

    candidates = find_candidates(env_paths, allow_tmp=args.allow_tmp)

    print('Discovered candidate paths:')
    for c in candidates:
        print('  ', c)
    if args.list:
        return 0

    # Build allowed bases list
    allowed = []
    for key in ('INTAKE_DIR','PROCESSED_DIR','ARCHIVE_DIR','FILING_CABINET_DIR','NORMALIZED_DIR'):
        v = env_paths.get(key)
        if v:
            allowed.append(Path(v))
    # include repo backup dirs
    repo_root = Path(__file__).resolve().parents[1]
    allowed.append(repo_root / 'db_prod_backups')
    allowed.append(repo_root / 'db_backups')
    allowed.append(dest_root)

    actions = []
    dry_run = not args.confirm

    # Safety check: refuse to operate if dest_root is inside repository unless force
    if dest_root.resolve().is_relative_to(repo_root.resolve()) and not args.force:
        print(f'WARNING: destination {dest_root} is inside the repository root {repo_root}.')
        print('Either set DB_BACKUP_DIR to a location outside the repo or pass --force to override.')
        return 3

    for src in candidates:
        # check allowed
        safe = is_within_allowed(src, allowed)
        if not safe and not args.force:
            print(f'SKIPPING (not within allowed bases): {src}')
            continue
        # perform copy/move into collected folder
        ac = copy_or_move(src, collected, do_move=args.confirm, dry_run=dry_run)
        for a in ac:
            print(a)
            actions.append(a)

    if args.tar:
        tar_path = dest_root / f'collected_backup_{timestamp}.tar.gz'
        if dry_run:
            print(f'DRY-RUN: would create tarball {tar_path} from {collected}')
        else:
            print(f'Creating tarball {tar_path}...')
            create_tarball(collected, tar_path)
            print('Tarball created:', tar_path)

    print('\nSUMMARY:')
    print('  dest:', collected)
    print('  actions:', len(actions))
    print('  dry_run:', dry_run)
    print('  tar_requested:', args.tar)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

import os
import time
from pathlib import Path
import pytest


@pytest.fixture(scope="session", autouse=True)
def _cleanup_repo_intake_after_tests():
    """If tests run against the repository intake directory, safely remove
    test-created sample files after the test session.

    Behaviour:
    - Snapshot files present at start; on teardown remove any new files that
      match conservative test patterns (contain 'sample' or start with 'test_'
      and have common document/image extensions).
    - Only operates when the intake dir is inside the repository to avoid
      accidental deletion of user data elsewhere.
    """
    start_time = time.time()
    intake_dir = os.environ.get('INTAKE_DIR') or str(Path(__file__).resolve().parents[2] / 'intake')
    initial = set()
    try:
        p = Path(intake_dir)
        if p.exists() and p.is_dir():
            for f in p.iterdir():
                try:
                    initial.add(f.resolve())
                except Exception:
                    continue
    except Exception:
        initial = set()

    yield

    # Teardown: remove conservative matches created during the test session
    try:
        p = Path(intake_dir)
        repo_root = Path(__file__).resolve().parents[2]
        # Safety: only operate if intake_dir is inside repo_root
        try:
            if not p.resolve().is_relative_to(repo_root.resolve()):
                return
        except Exception:
            try:
                p.resolve().relative_to(repo_root.resolve())
            except Exception:
                return

        if not p.exists() or not p.is_dir():
            return

        current = set()
        for f in p.iterdir():
            try:
                current.add(f.resolve())
            except Exception:
                continue

        new_files = current - initial
        for fpath in new_files:
            try:
                f = Path(fpath)
                if not f.exists() or not f.is_file():
                    continue
                name = f.name.lower()
                ext = f.suffix.lower()
                # conservative matching: sample*, test_* or name contains 'sample'
                if name.startswith('sample') or name.startswith('test_') or 'sample' in name:
                    # only remove common document/image extensions
                    if ext in ('.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff'):
                        try:
                            f.unlink()
                        except Exception:
                            # best-effort; skip if we cannot remove
                            continue
    except Exception:
        # Do not raise during teardown
        pass

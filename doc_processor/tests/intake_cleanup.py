import os
import time
from pathlib import Path
import pytest


@pytest.fixture(scope="session", autouse=True)
def _cleanup_repo_intake_after_tests():
    """Safely remove test-created sample files from the repo intake directory.

    This fixture snapshots existing files at test start and removes new files
    that match conservative patterns (contain 'sample' or start with 'test_'
    and have common document/image extensions) during teardown. It only
    operates when the intake directory is inside the repository root.
    """
    intake_dir = os.environ.get('INTAKE_DIR') or str(Path(__file__).resolve().parents[2] / 'intake')
    initial = set()

    try:
        p = Path(intake_dir)
        if p.exists() and p.is_dir():
            for f in p.iterdir():
                try:
                    initial.add(f.resolve())
                except Exception:
                    pass
    except Exception:
        initial = set()

    yield

    # Teardown: remove conservative matches created during the test session
    try:
        p = Path(intake_dir)
        repo_root = Path(__file__).resolve().parents[2]

        # Safety: ensure intake_dir is inside repository root
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

        for fpath in current - initial:
            try:
                f = Path(fpath)
                if not f.exists() or not f.is_file():
                    continue
                name = f.name.lower()
                ext = f.suffix.lower()

                if (name.startswith('sample') or name.startswith('test_') or 'sample' in name) and ext in ('.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff'):
                    try:
                        f.unlink()
                    except Exception:
                        pass
            except Exception:
                continue
    except Exception:
        # Never raise during test teardown
        pass

"""
Dry-run wrapper for `scripts/run_local_e2e.sh`.

This wrapper sets `TEST_TMPDIR` and related envs and then invokes the
original shell script using `subprocess` so it runs in a safe test-scoped
environment.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir():
        import tempfile
        return os.environ.get('TEST_TMPDIR') or os.environ.get('TMPDIR') or tempfile.gettempdir()

base = os.environ.get('TEST_TMPDIR') or select_tmp_dir()
Path(base).mkdir(parents=True, exist_ok=True)

os.environ.setdefault('TEST_TMPDIR', base)
os.environ.setdefault('INTAKE_DIR', str(Path(base) / 'intake'))
os.environ.setdefault('PROCESSED_DIR', str(Path(base) / 'processed'))

def main(argv=None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'run_local_e2e.sh'
    if not script.exists():
        raise FileNotFoundError(f'Original script not found: {script}')
    cmd = [str(script)] + (argv or [])
    return subprocess.call(cmd, env=os.environ)

if __name__ == '__main__':
    raise SystemExit(main())

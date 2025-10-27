"""Minimal local shim for python-dotenv used in tests and CI.

This project prefers importing from the installed `dotenv` package, but CI
and quick local runs may not have it available. A tiny shim that provides
`load_dotenv` is sufficient for configuration loading in tests that don't
depend on advanced dotenv features.

This file is intentionally minimal and only used for test/CI stability.
If you need full dotenv behavior locally, install `python-dotenv` in your
environment instead.
"""
from typing import Optional
import os

def load_dotenv(dotenv_path: Optional[str] = None, **kwargs) -> bool:
    """Best-effort no-op loader for .env files.

    If a path is provided, attempt to read lines of KEY=VALUE pairs and set
    them into the environment. Returns True if any variables were loaded,
    otherwise False.
    """
    loaded = False
    path = dotenv_path
    # If path is not provided, look for a `.env` in the current working dir
    if path is None:
        cwd = os.getcwd()
        default = os.path.join(cwd, '.env')
        if os.path.exists(default):
            path = default

    if path and os.path.exists(path):
        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        os.environ.setdefault(k, v)
                        loaded = True
        except Exception:
            # Swallow parsing errors; this shim is best-effort only
            return False
    return loaded

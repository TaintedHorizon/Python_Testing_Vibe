"""Local shim for python-dotenv used for CI/test stability.

This mirrors the small, minimal implementation previously added to the
repository root. Keeping it under `doc_processor/_shims/` avoids polluting
the repository root and makes it clear this is a test/CI compatibility shim.
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

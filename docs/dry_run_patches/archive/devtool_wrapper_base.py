"""
Small helper utilities used by the dry-run wrappers.

These wrappers live under `docs/dry_run_patches/applied/` and are intentionally
non-invasive: they set conservative test-safe defaults (using
`doc_processor.utils.path_utils.select_tmp_dir`) and then import and delegate to
the original implementation. They use `os.environ.setdefault` so they don't
override explicit user configuration.
"""
from __future__ import annotations

import os
import tempfile
from typing import Callable

from doc_processor.utils.path_utils import select_tmp_dir


def ensure_env_var_from_test(var_name: str, fallback_subdir: str | None = None) -> str:
    """Ensure environment variable is set to a test-safe location.

    - If the var is already set, leave it alone.
    - Otherwise, set it to TEST_TMPDIR (if defined) or a selected tmp dir under
      a per-repo prefix.

    Returns the final value.
    """
    if var_name in os.environ and os.environ.get(var_name):
        return os.environ[var_name]

    base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
    if fallback_subdir:
        path = os.path.join(base, fallback_subdir)
    else:
        path = os.path.join(base, "devtools")
    os.environ.setdefault(var_name, path)
    return os.environ[var_name]


def delegate_main(module_path: str) -> Callable[..., int]:
    """Import `module_path` and return a callable that runs its `main()`.

    The wrapper modules call `delegate_main("doc_processor.dev_tools.foo")()` so
    running the wrapper behaves like running the original script.
    """
    from importlib import import_module

    mod = import_module(module_path)

    def _run() -> int:
        if hasattr(mod, "main"):
            return mod.main()
        # Some dev scripts are modules meant to be executed; try calling
        # a top-level `run()` or simply return 0 if nothing to do.
        if hasattr(mod, "run"):
            return mod.run()
        return 0

    return _run

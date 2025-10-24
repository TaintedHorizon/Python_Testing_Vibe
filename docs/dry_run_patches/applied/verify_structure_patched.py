"""
Dry-run wrapper for `doc_processor.dev_tools.verify_structure`.

Ensures intake/processed dirs are test-scoped and delegates.
"""
import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir, ensure_dir
except Exception:
    def select_tmp_dir() -> str:
        return os.environ.get("TEST_TMPDIR") or os.environ.get("TMPDIR") or tempfile.gettempdir()

    def ensure_dir(p: str) -> None:
        os.makedirs(p, exist_ok=True)


base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
ensure_dir(base)

os.environ.setdefault("INTAKE_DIR", os.path.join(base, "intake"))
os.environ.setdefault("PROCESSED_DIR", os.path.join(base, "processed"))


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.verify_structure")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for `doc_processor.dev_tools.verify_structure`.

Sets directory paths used by the verifier to test-scoped locations so checks and
any repair actions don't modify real project folders during CI/tests.
"""

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir() -> str:
        return os.environ.get("TEST_TMPDIR") or os.environ.get("TMPDIR") or tempfile.gettempdir()

base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
os.makedirs(base, exist_ok=True)

os.environ.setdefault("PROCESSED_DIR", os.path.join(base, "processed"))
os.environ.setdefault("FILING_CABINET_DIR", os.path.join(base, "filing_cabinet"))

def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.verify_structure")
    if hasattr(mod, "main"):
        result = mod.main()
        return int(result or 0)
    if hasattr(mod, "run"):
        result = mod.run()
        return int(result or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for `doc_processor.dev_tools.verify_structure`.

Ensures verify outputs are placed under TEST_TMPDIR.
"""
import os

from doc_processor.utils.path_utils import select_tmp_dir


def ensure_env_var_from_test(var_name: str, fallback_subdir: str | None = None) -> str:
    if var_name in os.environ and os.environ.get(var_name):
        return os.environ[var_name]
    base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
    path = os.path.join(base, fallback_subdir or "devtools")
    os.environ.setdefault(var_name, path)
    return os.environ[var_name]


ensure_env_var_from_test("VERIFY_OUTPUT_DIR", "verify_structure")


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.verify_structure")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

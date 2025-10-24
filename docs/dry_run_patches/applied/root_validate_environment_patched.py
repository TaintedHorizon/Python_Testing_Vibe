"""
Dry-run wrapper for the repository `validate_environment.py` at the repo root.

Sets conservative test-scoped directories and delegates to the original module.
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

os.environ.setdefault("TEST_LOG_DIR", os.path.join(base, "logs"))
os.environ.setdefault("TEST_VENV_DIR", os.path.join(base, "venv"))


def _main() -> int:
    from importlib import import_module

    # Import repo-root script as a module by filename
    mod = import_module("validate_environment")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

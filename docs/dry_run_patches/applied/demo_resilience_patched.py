"""
Dry-run wrapper for `doc_processor.dev_tools.demo_resilience`.

Ensure any test artifacts are kept in TEST_TMPDIR.
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


ensure_env_var_from_test("DEMO_RESILIENCE_DIR", "demo_resilience")


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.demo_resilience")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

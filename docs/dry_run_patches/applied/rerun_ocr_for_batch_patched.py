"""
Dry-run wrapper for `doc_processor.dev_tools.rerun_ocr_for_batch`.

Routes processed output and temporary files to TEST_TMPDIR and delegates.
"""
import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir, ensure_dir
except Exception:  # pragma: no cover
    def select_tmp_dir() -> str:
        return os.environ.get("TEST_TMPDIR") or os.environ.get("TMPDIR") or tempfile.gettempdir()

    def ensure_dir(p: str) -> None:
        os.makedirs(p, exist_ok=True)


base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
ensure_dir(base)

# Redirect processed output and intake directories to test-scoped locations
os.environ.setdefault("PROCESSED_DIR", os.path.join(base, "processed"))
os.environ.setdefault("INTAKE_DIR", os.path.join(base, "intake"))


def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.rerun_ocr_for_batch")
    if hasattr(mod, "main"):
        return mod.main()
    if hasattr(mod, "run"):
        return mod.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
"""
Dry-run wrapper for `doc_processor.dev_tools.rerun_ocr_for_batch`.

Sets processed/intake paths to test-scoped locations (prefer `TEST_TMPDIR`) so
OCR re-runs during tests operate in temporary directories.
"""
from __future__ import annotations

import os
import tempfile

try:
    from doc_processor.utils.path_utils import select_tmp_dir
except Exception:
    def select_tmp_dir() -> str:
        return os.environ.get("TEST_TMPDIR") or os.environ.get("TMPDIR") or tempfile.gettempdir()

base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
os.makedirs(base, exist_ok=True)

os.environ.setdefault("INTAKE_DIR", os.path.join(base, "intake"))
os.environ.setdefault("PROCESSED_DIR", os.path.join(base, "processed"))
os.environ.setdefault("OCR_OUTPUT_DIR", os.path.join(base, "ocr_output"))

def _main() -> int:
    from importlib import import_module

    mod = import_module("doc_processor.dev_tools.rerun_ocr_for_batch")
    if hasattr(mod, "main"):
        return mod.main()
    """
    Dry-run wrapper for `doc_processor.dev_tools.rerun_ocr_for_batch`.

    Sets processed/intake and log paths to test-scoped locations (prefer
    `TEST_TMPDIR`) so OCR re-runs during tests operate in temporary directories and
    don't modify repository state.
    """

    import os
    import tempfile

    try:
        from doc_processor.utils.path_utils import select_tmp_dir
    except Exception:
        def select_tmp_dir() -> str:  # pragma: no cover - fallback
            return os.environ.get("TEST_TMPDIR") or os.environ.get("TMPDIR") or tempfile.gettempdir()

    base = os.environ.get("TEST_TMPDIR") or select_tmp_dir()
    os.makedirs(base, exist_ok=True)

    os.environ.setdefault("INTAKE_DIR", os.path.join(base, "intake"))
    os.environ.setdefault("PROCESSED_DIR", os.path.join(base, "processed"))
    os.environ.setdefault("LOG_FILE_PATH", os.path.join(base, "logs", "rerun_ocr_for_batch.log"))

    def _main() -> int:
        from importlib import import_module

        mod = import_module("doc_processor.dev_tools.rerun_ocr_for_batch")
        if hasattr(mod, "main"):
            result = mod.main()
            return int(result or 0)
        if hasattr(mod, "run"):
            result = mod.run()
            return int(result or 0)
        return 0


    if __name__ == "__main__":
        raise SystemExit(_main())

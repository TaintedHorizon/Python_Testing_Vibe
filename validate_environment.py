#!/usr/bin/env python3
"""
Root shim: delegate to the canonical implementation at `scripts/validate_environment.py`.

This small script keeps `validate_environment.py` discoverable at the repository root
while the authoritative implementation lives under `scripts/`.
"""

from importlib import import_module
import sys


def main() -> int:
    try:
        mod = import_module("scripts.validate_environment")
        if hasattr(mod, "main"):
            return mod.main()
        print("Error: scripts.validate_environment does not expose main()", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - trivial delegating shim
        print(f"Error invoking scripts.validate_environment: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
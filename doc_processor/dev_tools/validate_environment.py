#!/usr/bin/env python3
"""Environment validation script (moved under dev_tools).

Ensures AI assistants and developers follow canonical patterns defined in
`.github/copilot-instructions.md`.
"""
from __future__ import annotations
import os, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

def check_environment():
    issues: list[str] = []
    warnings: list[str] = []

    if not REPO_ROOT.exists():
        issues.append("❌ Repository root not found at expected path")
        return issues, warnings

    # Startup script
    startup = REPO_ROOT / 'start_app.sh'
    if not startup.exists():
        issues.append("❌ Missing start_app.sh (required entrypoint)")
    elif not os.access(startup, os.X_OK):
        warnings.append("⚠️ start_app.sh not executable (chmod +x start_app.sh)")

    venv = REPO_ROOT / 'doc_processor' / 'venv'
    if not venv.exists():
        issues.append("❌ Virtual environment missing at doc_processor/venv")

    cfg = REPO_ROOT / 'doc_processor' / 'config_manager.py'
    if not cfg.exists():
        issues.append("❌ config_manager.py missing (central config)")

    legacy_cfg = REPO_ROOT / 'doc_processor' / 'config.py'
    if legacy_cfg.exists():
        warnings.append("⚠️ Legacy config.py still present – should be removed")

    env_file = REPO_ROOT / 'doc_processor' / '.env'
    env_sample = REPO_ROOT / 'doc_processor' / '.env.sample'
    if not env_file.exists() and env_sample.exists():
        warnings.append("⚠️ .env missing – copy from .env.sample for proper config")

    copilot = REPO_ROOT / '.github' / 'copilot-instructions.md'
    if not copilot.exists():
        warnings.append("⚠️ Missing .github/copilot-instructions.md")

    return issues, warnings

def main() -> int:
    print("🔍 Validating environment (dev_tools/validate_environment.py)...\n")
    issues, warnings = check_environment()
    if issues:
        print("🚨 CRITICAL ISSUES:")
        for i in issues: print('  ' + i)
        print()
    if warnings:
        print("⚠️ WARNINGS:")
        for w in warnings: print('  ' + w)
        print()
    if not issues and not warnings:
        print("✅ Environment validation passed – no issues or warnings.")
    elif not issues:
        print("✅ No critical issues. Address warnings for optimal setup.")
    else:
        print("❌ Critical issues detected – see .github/copilot-instructions.md")
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
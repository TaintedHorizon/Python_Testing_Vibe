#!/usr/bin/env python3
"""
Environment validation script to ensure AI assistants follow correct patterns.
This script checks for common mistakes outlined in .github/copilot-instructions.md
"""

import os
import sys
from pathlib import Path

def check_environment():
    """Check if the environment is set up correctly."""
    issues = []
    warnings = []

    # Check if we're in the right directory
    repo_root = Path("/home/svc-scan/Python_Testing_Vibe")
    if not repo_root.exists():
        issues.append("❌ Repository not found at expected location")
        return issues, warnings

    # Check for startup script
    startup_script = repo_root / "start_app.sh"
    if not startup_script.exists():
        issues.append("❌ start_app.sh not found - use ./start_app.sh to run app")
    else:
        if not os.access(startup_script, os.X_OK):
            warnings.append("⚠️ start_app.sh is not executable - run: chmod +x start_app.sh")

    # Check virtual environment location
    venv_path = repo_root / "doc_processor" / "venv"
    if not venv_path.exists():
        issues.append("❌ Virtual environment not found at doc_processor/venv/")

    # Check for config_manager.py (not config.py)
    config_manager = repo_root / "doc_processor" / "config_manager.py"
    old_config = repo_root / "doc_processor" / "config.py"

    if not config_manager.exists():
        issues.append("❌ config_manager.py not found")

    if old_config.exists():
        warnings.append("⚠️ Old config.py exists - should use config_manager.py instead")

    # Check for .env file
    env_file = repo_root / "doc_processor" / ".env"
    env_sample = repo_root / "doc_processor" / ".env.sample"

    if not env_file.exists() and env_sample.exists():
        warnings.append("⚠️ .env file not found - copy from .env.sample")

    # Check for copilot instructions
    instructions = repo_root / ".github" / "copilot-instructions.md"
    if not instructions.exists():
        warnings.append("⚠️ AI assistant instructions not found")

    return issues, warnings

def main():
    print("🔍 Validating Python_Testing_Vibe environment...")
    print("📋 Checking patterns from .github/copilot-instructions.md\n")

    issues, warnings = check_environment()

    if issues:
        print("🚨 CRITICAL ISSUES:")
        for issue in issues:
            print(f"  {issue}")
        print()

    if warnings:
        print("⚠️ WARNINGS:")
        for warning in warnings:
            print(f"  {warning}")

    if not issues and not warnings:
        print("✅ Environment validation passed!")
        print("🎯 All critical patterns are correctly configured.")
    elif not issues:
        print("✅ No critical issues found.")
        print("💡 Address warnings for optimal setup.")
    else:
        print("❌ Critical issues found - see .github/copilot-instructions.md")
        return 1

    print("\n📖 For AI assistants: Follow patterns in .github/copilot-instructions.md")
    return 0

if __name__ == "__main__":
    sys.exit(main())

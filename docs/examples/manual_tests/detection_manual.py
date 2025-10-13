#!/usr/bin/env python3
"""
Manual document detection diagnostic script (archived).

This file was moved from `doc_processor/dev_tools/test_detection.py` and
kept as a manual example. It is intentionally not named with a `test_` prefix
so pytest will not automatically collect it.

Usage: run manually from repo root with the venv active.
"""
import os

from doc_processor.document_detector import get_detector
from doc_processor.config_manager import app_config


def simulate_filenames():
    detector = get_detector()
    test_cases = [
        ("invoice_2024_001.pdf", "single"),
        ("scan_20240325.pdf", "batch"),
        ("document.pdf", "batch"),
    ]
    for filename, expected in test_cases:
        hint = detector._analyze_filename(filename.replace('.pdf', ''))
        predicted = "single" if hint == "single" else "batch"
        print(f"{filename}: expected={expected}, predicted={predicted}, hint={hint}")


def analyze_intake():
    detector = get_detector()
    if not os.path.isdir(app_config.INTAKE_DIR):
        print(f"Intake directory not found: {app_config.INTAKE_DIR} - skipping real-file analysis")
        return
    analyses = detector.analyze_intake_directory(app_config.INTAKE_DIR)
    for a in analyses:
        print(f"{os.path.basename(a.file_path)} -> strategy={a.processing_strategy} confidence={a.confidence}")


if __name__ == '__main__':
    print("Detection manual diagnostics")
    simulate_filenames()
    analyze_intake()

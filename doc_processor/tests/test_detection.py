import os
import pytest

from doc_processor.document_detector import get_detector
from doc_processor.config_manager import app_config


def test_filename_heuristics_unit():
    """Unit test for filename pattern heuristics (fast, deterministic).

    This test exercises the _analyze_filename helper directly with a set of
    representative filenames. It avoids any file system dependencies and
    therefore runs fast in CI.
    """
    detector = get_detector()

    cases = [
        ("invoice_2024_001.pdf", "single"),
        ("contract_lease_2024.pdf", "single"),
        ("scan_20240325.pdf", "batch"),
        ("document.pdf", "batch"),
        ("random_name.pdf", "batch"),
    ]

    for fname, expected in cases:
        hint = detector._analyze_filename(fname.replace('.pdf', ''))
        predicted = "single" if hint == "single" else "batch"
        assert predicted == expected, f"Filename {fname} predicted {predicted}, expected {expected}"


def test_detection_integration_skip_if_no_intake_dir():
    """Integration smoke: analyze intake directory only if present (non-blocking).

    This test is intentionally permissive: if the intake dir isn't present or
    empty in the test environment, the test will be skipped rather than fail.
    """
    detector = get_detector()
    if not os.path.isdir(app_config.INTAKE_DIR):
        pytest.skip(f"Intake dir not found: {app_config.INTAKE_DIR}")
    analyses = detector.analyze_intake_directory(app_config.INTAKE_DIR)
    if not analyses:
        pytest.skip("No files in intake dir to analyze")
    assert isinstance(analyses, list)

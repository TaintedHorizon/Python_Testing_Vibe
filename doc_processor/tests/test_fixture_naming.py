import os
from pathlib import Path


def test_e2e_fixture_naming_convention():
    fixtures_dir = Path(__file__).resolve().parent / "e2e" / "fixtures"
    if not fixtures_dir.exists():
        # No fixtures directory; test is not applicable
        return
    files = [p.name for p in fixtures_dir.iterdir() if p.is_file()]
    assert files, "No e2e fixtures found"
    bad = [f for f in files if not f.startswith("sample_")]
    assert not bad, f"E2E fixture files must start with 'sample_': {bad}"

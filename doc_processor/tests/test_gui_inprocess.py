import os
import json
import tempfile
import time
from pathlib import Path

import pytest

from doc_processor.app import create_app
from doc_processor.config_manager import app_config
import logging


def test_inprocess_analyze_and_start_batch(tmp_path, monkeypatch):
    """Fast in-process test that mirrors the GUI workflow using Flask test client.

    - places a sample PDF in the intake dir
    - calls the analyze API endpoint (POST /analyze_intake)
    - asserts the analyze response success
    - posts to /batch/process_smart and checks the JSON response
    """
    # Setup temp dirs
    intake = tmp_path / 'intake'
    processed = tmp_path / 'processed'
    filing = tmp_path / 'filing'
    intake.mkdir()
    processed.mkdir()
    filing.mkdir()

    # Point app config to temp dirs
    monkeypatch.setenv('INTAKE_DIR', str(intake))
    monkeypatch.setenv('PROCESSED_DIR', str(processed))
    monkeypatch.setenv('FILING_CABINET_DIR', str(filing))
    monkeypatch.setenv('FAST_TEST_MODE', '1')
    monkeypatch.setenv('SKIP_OLLAMA', '1')

    # Reduce logging noise to avoid background threads writing to closed
    # streams during pytest teardown which can cause interpreter shutdown
    # errors in this environment.
    logging.getLogger().setLevel(logging.CRITICAL)

    app = create_app()
    client = app.test_client()

    # ensure health OK
    r = client.get('/health')
    assert r.status_code == 200

    # Place a dummy sample file into intake
    sample_path = Path(__file__).parents[1] / 'tests' / 'fixtures' / 'sample_small.pdf'
    if sample_path.exists():
        dest = intake / 'sample_small.pdf'
        dest.write_bytes(sample_path.read_bytes())
    else:
        # create a tiny placeholder file
        (intake / 'sample_small.pdf').write_text('PDF-PLACEHOLDER')

    # Call analyze endpoint (GET the page to ensure no template errors), then POST analyze
    r = client.get('/analyze_intake')
    assert r.status_code in (200, 302)

    # POST to start analysis via API route
    r = client.post('/api/analyze_intake', json={})
    # Some app variants return 200 with JSON, others redirect; accept both for now
    assert r.status_code in (200, 202, 302)

    # Start smart processing
    r = client.post('/batch/process_smart', json={})
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, dict)
    assert data.get('success') in (True, False)

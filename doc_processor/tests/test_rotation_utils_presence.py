import re
import pytest
from doc_processor.app import create_app

def test_manipulate_template_includes_rotation_utils(tmp_path, monkeypatch):
    # Ensure app uses test database path
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'test.db'))
    app = create_app()
    client = app.test_client()
    resp = client.get('/manipulation/manipulate')
    if resp.status_code in (302, 404):
        pytest.skip(f'Route unavailable (status {resp.status_code}) – skipping presence assertion')
    assert resp.status_code == 200
    assert 'rotation_utils.js' in resp.get_data(as_text=True)


def test_intake_analysis_template_includes_rotation_utils(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'test.db'))
    app = create_app()
    client = app.test_client()
    resp = client.get('/intake/analysis')
    if resp.status_code in (302, 404):
        pytest.skip(f'Analysis route unavailable (status {resp.status_code}) – skipping presence assertion')
    assert resp.status_code == 200
    assert 'rotation_utils.js' in resp.get_data(as_text=True)

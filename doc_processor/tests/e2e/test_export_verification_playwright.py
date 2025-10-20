import os
import pytest


@pytest.mark.skipif(os.getenv('PLAYWRIGHT_E2E', '0') != '1', reason='Playwright E2E disabled')
def test_export_verification(app_process, e2e_page, e2e_artifacts_dir):
    """Scaffold: trigger export via UI and verify exported files and metadata in filing cabinet.

    TODO: implement export trigger and verification.
    """
    pytest.skip('Scaffold — implement export trigger and verification')

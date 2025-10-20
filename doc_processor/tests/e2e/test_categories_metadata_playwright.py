import os
import pytest


@pytest.mark.skipif(os.getenv('PLAYWRIGHT_E2E', '0') != '1', reason='Playwright E2E disabled')
def test_categories_metadata_can_be_set(app_process, e2e_page, e2e_artifacts_dir):
    """Scaffold: set a category on a document and assert it persists in the UI and DB.

    TODO: implement full interactions with category UI controls, save, and verify.
    """
    pytest.skip('Scaffold — implement category setting interactions')

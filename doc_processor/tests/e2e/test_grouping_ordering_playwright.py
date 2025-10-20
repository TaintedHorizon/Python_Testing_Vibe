import os
import pytest


@pytest.mark.skipif(os.getenv('PLAYWRIGHT_E2E', '0') != '1', reason='Playwright E2E disabled')
def test_grouping_and_ordering_flow(app_process, e2e_page, e2e_artifacts_dir):
    """Scaffold: exercise grouping multiple documents, reordering, and verify final export order.

    TODO: implement grouping UI interactions (drag/drop or controls) and export checks.
    """
    pytest.skip('Scaffold — implement grouping and ordering interactions')

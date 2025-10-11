import os
import sys
import pytest
from doc_processor.config_manager import app_config

def test_database_path_consistency(tmp_path):
    # Ensure that DATABASE_PATH resolves consistently across working directories
    test_dirs = [
        os.getcwd(),
        os.path.join(os.getcwd(), 'doc_processor'),
        '/tmp'
    ]
    abs_paths = set()
    for d in test_dirs:
        old = os.getcwd()
        try:
            os.chdir(d)
            p = os.path.abspath(app_config.DATABASE_PATH)
            abs_paths.add(p)
        finally:
            os.chdir(old)
    assert len(abs_paths) == 1

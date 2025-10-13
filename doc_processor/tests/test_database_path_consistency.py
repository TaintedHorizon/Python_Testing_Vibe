import os
from doc_processor.config_manager import app_config

def test_database_path_consistency(tmp_path):
    # Ensure that DATABASE_PATH resolves consistently across common working directories.
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    test_dirs = [
        os.getcwd(),
        os.path.join(repo_root, 'doc_processor'),
        '/tmp'
    ]
    abs_paths = set()
    for d in test_dirs:
        if not os.path.isdir(d):
            # skip non-existent candidate directories to avoid FileNotFoundError
            continue
        old = os.getcwd()
        try:
            os.chdir(d)
            p = os.path.abspath(app_config.DATABASE_PATH)
            abs_paths.add(p)
        finally:
            os.chdir(old)
    assert len(abs_paths) == 1

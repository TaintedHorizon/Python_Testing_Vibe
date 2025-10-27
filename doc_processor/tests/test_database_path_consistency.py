import os
import tempfile
# Ensure an absolute, test-scoped DATABASE_PATH is set early (before config
# is imported) so that any module reading configuration during import sees a
# deterministic path. Use a per-process temp DB to avoid collisions.
os.environ.setdefault('DATABASE_PATH', os.path.join(tempfile.gettempdir(), f'doc_processor_test_{os.getpid()}.db'))
from doc_processor.config_manager import app_config


def test_database_path_consistency(tmp_path):
    # Ensure that DATABASE_PATH resolves consistently across common working directories.
    # Make the test hermetic by forcing DATABASE_PATH to a temp file so
    # environment differences (pre-existing /tmp/documents.db) don't break CI.
    old_db = app_config.DATABASE_PATH
    try:
        # Also set to tmp_path for this test invocation (absolute path)
        app_config.DATABASE_PATH = str((tmp_path / "documents.db").resolve())
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        test_dirs = [
            os.getcwd(),
            os.path.join(repo_root, 'doc_processor'),
            tempfile.gettempdir()
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
    finally:
        # restore original config to avoid side-effects for other tests
        app_config.DATABASE_PATH = old_db

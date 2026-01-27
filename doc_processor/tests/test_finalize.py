import os
from pathlib import Path
import tempfile
import shutil
import sqlite3
import pytest

from doc_processor.processing import finalize_single_documents_batch_with_progress
from doc_processor.database import get_db_connection
from config_manager import app_config


@pytest.fixture()
def tmp_env_dirs(tmp_path):
    root = tmp_path / 'e2e_test'
    intake = root / 'intake'
    processed = root / 'processed'
    filing = root / 'filing_cabinet'
    intake.mkdir(parents=True)
    processed.mkdir(parents=True)
    filing.mkdir(parents=True)
    orig_db = app_config.DATABASE_PATH
    db_path = str(root / 'documents.db')
    os.environ['DATABASE_PATH'] = db_path
    # ensure config_manager picks this up via get_db_connection; create DB by connecting
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE IF NOT EXISTS batches (id INTEGER PRIMARY KEY AUTOINCREMENT, status TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS single_documents (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER, original_filename TEXT, original_pdf_path TEXT, searchable_pdf_path TEXT, status TEXT, ocr_text TEXT)')
    conn.commit()
    conn.close()
    # patch app_config paths for this run
    app_config.INTAKE_DIR = str(intake)
    app_config.PROCESSED_DIR = str(processed)
    app_config.FILING_CABINET_DIR = str(filing)
    yield {'root': str(root), 'db': db_path, 'intake': str(intake), 'processed': str(processed), 'filing': str(filing)}
    # cleanup
    try:
        shutil.rmtree(str(root))
    except Exception:
        pass
    os.environ.pop('DATABASE_PATH', None)
    app_config.FILING_CABINET_DIR = 'filing_cabinet'


def test_finalize_happy_path(tmp_env_dirs):
    # Create a fake original and searchable PDF files
    intake = tmp_env_dirs['intake']
    processed = tmp_env_dirs['processed']
    filing = tmp_env_dirs['filing']
    db_path = tmp_env_dirs['db']

    original = os.path.join(intake, 'doc1.pdf')
    searchable = os.path.join(processed, '1', 'searchable_pdfs', 'doc1_searchable.pdf')
    os.makedirs(os.path.dirname(searchable), exist_ok=True)
    from .test_utils import write_valid_pdf
    write_valid_pdf(Path(original))
    write_valid_pdf(Path(searchable))

    # Insert batch and single_documents row
    from doc_processor.database import get_or_create_test_batch
    batch_id = get_or_create_test_batch('finalize_tests')
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO single_documents (batch_id, original_filename, original_pdf_path, searchable_pdf_path, status) VALUES (?,?,?,?, 'completed')", (batch_id, 'doc1.pdf', original, searchable))
    conn.commit()
    conn.close()

    # Run finalize
    ok = finalize_single_documents_batch_with_progress(batch_id, lambda c, t, m, d: None)
    assert ok

    # check filing cabinet contains the files
    entries = os.listdir(filing)
    assert entries, 'Filing cabinet empty after finalize'
    # Check category subdir and files
    cat_dir = os.path.join(filing, 'Uncategorized')
    assert os.path.isdir(cat_dir)
    files = os.listdir(cat_dir)
    assert any(f.endswith('_original.pdf') for f in files)
    assert any(f.endswith('_searchable.pdf') for f in files)


def test_finalize_missing_searchable_creates_fallback(tmp_env_dirs):
    intake = tmp_env_dirs['intake']
    processed = tmp_env_dirs['processed']
    filing = tmp_env_dirs['filing']
    db_path = tmp_env_dirs['db']

    original = os.path.join(intake, 'doc2.pdf')
    # Note: no searchable created
    from .test_utils import write_valid_pdf
    write_valid_pdf(Path(original))

    from doc_processor.database import get_or_create_test_batch
    batch_id = get_or_create_test_batch('finalize_tests')
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO single_documents (batch_id, original_filename, original_pdf_path, searchable_pdf_path, status) VALUES (?,?,?,?, 'completed')", (batch_id, 'doc2.pdf', original, None))
    conn.commit()
    conn.close()

    ok = finalize_single_documents_batch_with_progress(batch_id, lambda c, t, m, d: None)
    assert ok
    # fallback should have copied original to searchable dest
    cat_dir = os.path.join(filing, 'Uncategorized')
    files = os.listdir(cat_dir)
    assert any(f.endswith('_searchable.pdf') for f in files), 'Missing searchable fallback in filing cabinet'

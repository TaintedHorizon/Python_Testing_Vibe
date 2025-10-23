#!/usr/bin/env python3
"""
Manual progress tracking diagnostic script (archived).

This was moved from `doc_processor/dev_tools/test_progress_tracking.py` and
renamed to avoid pytest collection. Use manually when debugging progress events.
"""
from doc_processor.processing import _process_single_documents_as_batch_with_progress
from doc_processor.document_detector import DocumentAnalysis
import os


def run_progress_demo():
    import tempfile
    tmp = tempfile.gettempdir()
    mock_docs = [
        DocumentAnalysis(file_path=os.path.join(tmp, 'test1.pdf'), file_size_mb=1.2, page_count=2, processing_strategy='single_document', confidence=0.9, reasoning=['sample']),
    ]
    for update in _process_single_documents_as_batch_with_progress(mock_docs):
        print('Update:', update)


if __name__ == '__main__':
    run_progress_demo()

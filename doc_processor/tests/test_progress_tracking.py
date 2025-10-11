from doc_processor.processing import _process_single_documents_as_batch_with_progress
from doc_processor.document_detector import DocumentAnalysis


def test_progress_generator_yields_expected_keys(monkeypatch, tmp_path):
    """Create synthetic DocumentAnalysis input and verify generator yields progress dicts."""
    # Create two synthetic (non-existing) file analyses to exercise flow that yields events.
    docs = [
        DocumentAnalysis(file_path=str(tmp_path / "file1.pdf"), file_size_mb=0.1, page_count=1, processing_strategy='single_document', confidence=0.9, reasoning=['sample']),
        DocumentAnalysis(file_path=str(tmp_path / "file2.pdf"), file_size_mb=0.2, page_count=2, processing_strategy='single_document', confidence=0.85, reasoning=['sample']),
    ]

    events = list(_process_single_documents_as_batch_with_progress(docs))
    # At minimum we expect an initial batch_id event and at least some document_start or error events
    assert any('batch_id' in e for e in events), f"No batch_id event in {events}"
    # Ensure event dictionaries contain expected keys when present
    for e in events:
        assert isinstance(e, dict)
        # allowed keys: batch_id, document_start, document_complete, error, message
        allowed = {
            'batch_id', 'document_start', 'document_complete', 'error', 'message',
            'filename', 'document_number', 'total_documents', 'category', 'ai_name', 'confidence', 'documents_completed'
        }
        assert set(e.keys()).issubset(allowed), f"Unexpected keys in event: {e.keys()}"

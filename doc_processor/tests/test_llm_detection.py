from doc_processor.document_detector import get_detector

def test_llm_detector_instantiation():
    d1 = get_detector(use_llm_for_ambiguous=True)
    d2 = get_detector(use_llm_for_ambiguous=False)
    assert d1 is not None and d2 is not None

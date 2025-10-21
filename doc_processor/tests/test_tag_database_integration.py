#!/usr/bin/env python3
"""
Tag database integration tests moved from dev_tools.
"""
import logging
import pytest

pytestmark = pytest.mark.usefixtures('allow_db_creation')

from doc_processor.database import (
    store_document_tags, get_document_tags, find_similar_documents_by_tags,
    get_tag_usage_stats, analyze_tag_classification_patterns, get_db_connection
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def create_test_document():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from doc_processor.database import get_or_create_test_batch
        batch_id = get_or_create_test_batch('tag_db_integration')
        cursor.execute(
            """
            INSERT INTO single_documents (
                batch_id, original_filename, page_count, ocr_text,
                ai_suggested_category, final_category, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                "test_invoice.pdf",
                1,
                "INVOICE\nABC Company\n123 Main Street\nBill To: John Smith\nAmount: $1,500.00\nInvoice #12345\nDate: 2024-01-15",
                "Financial Document",
                "Financial Document",
                "finalized"
            )
        )
        document_id = cursor.lastrowid
        conn.commit()
        logging.info(f"✓ Created test document with ID: {document_id}")
        return document_id, batch_id
    except Exception as e:
        logging.error(f"Failed to create test document: {e}")
        conn.rollback()
        return None, None
    finally:
        conn.close()


def test_tag_storage_and_retrieval():
    document_id, batch_id = create_test_document()
    assert document_id, "Failed to create test document"

    test_tags = {
        'people': ['John Smith'],
        'organizations': ['ABC Company'],
        'places': ['123 Main Street'],
        'dates': ['2024-01-15'],
        'document_types': ['invoice'],
        'keywords': ['billing', 'payment'],
        'amounts': ['$1,500.00'],
        'reference_numbers': ['12345']
    }

    tags_stored = store_document_tags(document_id, test_tags)
    assert tags_stored > 0

    retrieved_tags = get_document_tags(document_id)
    expected_categories = set(test_tags.keys())
    retrieved_categories = set(retrieved_tags.keys())
    assert expected_categories == retrieved_categories

    for category, expected_values in test_tags.items():
        retrieved_values = retrieved_tags.get(category, [])
        for value in expected_values:
            assert value in retrieved_values


def test_similar_document_search():
    # Create additional documents and tags
    doc_id_1, _ = create_test_document()
    if doc_id_1:
        tags_1 = {
            'people': ['Jane Doe'],
            'organizations': ['ABC Company'],
            'places': ['456 Oak Avenue'],
            'dates': ['2024-01-20'],
            'document_types': ['invoice'],
            'keywords': ['billing', 'payment'],
            'amounts': ['$2,000.00'],
            'reference_numbers': ['12346']
        }
        store_document_tags(doc_id_1, tags_1)

    doc_id_2, _ = create_test_document()
    if doc_id_2:
        tags_2 = {
            'people': ['Bob Johnson'],
            'organizations': ['ABC Company'],
            'places': ['789 Pine Street'],
            'dates': ['2024-01-25'],
            'document_types': ['contract'],
            'keywords': ['agreement', 'terms'],
            'amounts': ['$5,000.00'],
            'reference_numbers': ['CON001']
        }
        store_document_tags(doc_id_2, tags_2)

    search_tags = {
        'organizations': ['ABC Company'],
        'document_types': ['invoice']
    }

    similar_docs = find_similar_documents_by_tags(search_tags, limit=5, min_tag_matches=1)
    assert len(similar_docs) >= 2


def test_tag_usage_stats_and_pattern_analysis():
    stats = get_tag_usage_stats(limit=20)
    assert isinstance(stats, list)
    org_stats = get_tag_usage_stats(category='organizations', limit=10)
    assert isinstance(org_stats, list)

    analysis = analyze_tag_classification_patterns()
    assert 'pattern_count' in analysis


def test_database_constraints():
    document_id, _ = create_test_document()
    assert document_id

    duplicate_tags = {
        'people': ['John Smith', 'John Smith'],
        'organizations': ['ABC Company']
    }
    tags_stored = store_document_tags(document_id, duplicate_tags)
    retrieved_tags = get_document_tags(document_id)
    assert len(retrieved_tags['people']) == 1 and 'John Smith' in retrieved_tags['people']

    empty_tags = {
        'people': [],
        'organizations': ['XYZ Corp'],
        'places': [''],
        'dates': None
    }
    tags_stored = store_document_tags(document_id, empty_tags)
    retrieved_tags = get_document_tags(document_id)
    assert ('XYZ Corp' in retrieved_tags.get('organizations', []))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO document_tags (document_id, tag_category, tag_value)
            VALUES (?, ?, ?)
        """, (document_id, 'invalid_category', 'test_value'))
        conn.commit()
        pytest.fail("Invalid category was accepted - constraint not working")
    except Exception:
        pass
    finally:
        conn.close()

import pytest

@pytest.mark.usefixtures('temp_db_path')
def test_tag_storage_and_retrieval():
    conn = get_db_connection()
    cur = conn.cursor()
    from doc_processor.database import get_or_create_test_batch
    batch_id = get_or_create_test_batch('tag_db_integration')
    cur.execute("INSERT INTO single_documents (batch_id, original_filename, page_count, status) VALUES (?,?,?,?)",
                (batch_id, 'test.pdf', 1, 'finalized'))
    doc_id = cur.lastrowid
    conn.commit()

    tags = {'people': ['John Smith'], 'organizations': ['ACME']}
    stored = store_document_tags(doc_id, tags)
    assert stored >= 1
    retrieved = get_document_tags(doc_id)
    assert 'people' in retrieved

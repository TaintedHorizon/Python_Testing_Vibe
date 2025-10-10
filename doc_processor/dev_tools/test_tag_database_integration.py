#!/usr/bin/env python3
"""
Test script for tag database integration functionality.

This script tests:
1. Tag storage and retrieval
2. Tag-based similarity search
3. Tag usage statistics and analysis
4. Database integrity and constraints
"""

import sys
import os
import json
import logging
import tempfile
from datetime import datetime

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import (
    store_document_tags, get_document_tags, find_similar_documents_by_tags,
    get_tag_usage_stats, analyze_tag_classification_patterns, get_db_connection
)

import pytest


@pytest.fixture(autouse=True)
def _use_temp_db(monkeypatch, tmp_path):
    """Automatically use a temporary DATABASE_PATH for these dev tools scripts."""
    tmp_db = tmp_path / f"tag_db_{os.getpid()}.db"
    monkeypatch.setenv('DATABASE_PATH', str(tmp_db))
    monkeypatch.setenv('ALLOW_NEW_DB', '1')
    yield

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def create_test_document():
    """Create a test document in single_documents table for testing."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create a test batch first
        cursor.execute("""
            INSERT INTO batches (status) VALUES ('testing')
        """)
        batch_id = cursor.lastrowid
        
        # Create a test single document
        cursor.execute("""
            INSERT INTO single_documents (
                batch_id, original_filename, page_count, ocr_text,
                ai_suggested_category, final_category, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            batch_id,
            "test_invoice.pdf",
            1,
            "INVOICE\nABC Company\n123 Main Street\nBill To: John Smith\nAmount: $1,500.00\nInvoice #12345\nDate: 2024-01-15",
            "Financial Document",
            "Financial Document", 
            "finalized"
        ))
        
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
    """Test storing and retrieving tags."""
    logging.info("\n=== Testing Tag Storage and Retrieval ===")
    
    # Create test document
    document_id, batch_id = create_test_document()
    if not document_id:
        logging.error("Failed to create test document")
        return False
    
    # Sample extracted tags
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
    
    try:
        # Test tag storage
        tags_stored = store_document_tags(document_id, test_tags)
        logging.info(f"✓ Stored {tags_stored} tags successfully")
        
        if tags_stored != 8:  # Should store exactly 8 tags (one per category)
            logging.warning(f"Expected 8 tags, but stored {tags_stored}")
        
        # Test tag retrieval
        retrieved_tags = get_document_tags(document_id)
        logging.info(f"✓ Retrieved tags: {retrieved_tags}")
        
        # Verify all categories are present
        expected_categories = set(test_tags.keys())
        retrieved_categories = set(retrieved_tags.keys())
        
        if expected_categories != retrieved_categories:
            logging.error(f"Category mismatch. Expected: {expected_categories}, Got: {retrieved_categories}")
            return False
        
        # Verify tag values
        for category, expected_values in test_tags.items():
            retrieved_values = retrieved_tags.get(category, [])
            for value in expected_values:
                if value not in retrieved_values:
                    logging.error(f"Missing tag value '{value}' in category '{category}'")
                    return False
        
        logging.info("✅ Tag storage and retrieval test PASSED")
        return True
        
    except Exception as e:
        logging.error(f"Tag storage/retrieval test FAILED: {e}")
        return False

def test_similar_document_search():
    """Test finding similar documents by tags."""
    logging.info("\n=== Testing Similar Document Search ===")
    
    # Create additional test documents with overlapping tags
    document_ids = []
    
    # Document 1: Similar invoice
    doc_id_1, _ = create_test_document()
    if doc_id_1:
        tags_1 = {
            'people': ['Jane Doe'],
            'organizations': ['ABC Company'],  # Same company
            'places': ['456 Oak Avenue'],
            'dates': ['2024-01-20'],
            'document_types': ['invoice'],  # Same type
            'keywords': ['billing', 'payment'],  # Same keywords
            'amounts': ['$2,000.00'],
            'reference_numbers': ['12346']
        }
        store_document_tags(doc_id_1, tags_1)
        document_ids.append(doc_id_1)
    
    # Document 2: Different type but same organization
    doc_id_2, _ = create_test_document()
    if doc_id_2:
        tags_2 = {
            'people': ['Bob Johnson'],
            'organizations': ['ABC Company'],  # Same company
            'places': ['789 Pine Street'],
            'dates': ['2024-01-25'],
            'document_types': ['contract'],  # Different type
            'keywords': ['agreement', 'terms'],
            'amounts': ['$5,000.00'],
            'reference_numbers': ['CON001']
        }
        store_document_tags(doc_id_2, tags_2)
        document_ids.append(doc_id_2)
    
    # Test similarity search
    search_tags = {
        'organizations': ['ABC Company'],
        'document_types': ['invoice']
    }
    
    try:
        similar_docs = find_similar_documents_by_tags(search_tags, limit=5, min_tag_matches=1)
        logging.info(f"✓ Found {len(similar_docs)} similar documents")
        
        for doc in similar_docs:
            logging.info(f"  - Document {doc['document_id']}: {doc['tag_matches']} matching tags in '{doc['tag_category']}'")
            logging.info(f"    Matching tags: {doc['matching_tags']}")
        
        # Should find at least 2 documents (both have ABC Company)
        if len(similar_docs) >= 2:
            logging.info("✅ Similar document search test PASSED")
            return True
        else:
            logging.error(f"Expected at least 2 similar documents, found {len(similar_docs)}")
            return False
            
    except Exception as e:
        logging.error(f"Similar document search test FAILED: {e}")
        return False

def test_tag_usage_stats():
    """Test tag usage statistics."""
    logging.info("\n=== Testing Tag Usage Statistics ===")
    
    try:
        # Get overall tag usage stats
        stats = get_tag_usage_stats(limit=20)
        logging.info(f"✓ Retrieved {len(stats)} tag usage statistics")
        
        if stats:
            logging.info("Top tag usage:")
            for stat in stats[:5]:  # Show top 5
                logging.info(f"  - {stat['tag_category']}: {stat['tag_value']} (used {stat['usage_count']} times)")
        
        # Get stats for specific category
        org_stats = get_tag_usage_stats(category='organizations', limit=10)
        logging.info(f"✓ Retrieved {len(org_stats)} organization tag statistics")
        
        if org_stats:
            logging.info("Organization tags:")
            for stat in org_stats:
                logging.info(f"  - {stat['tag_value']}: {stat['usage_count']} documents")
        
        logging.info("✅ Tag usage statistics test PASSED")
        return True
        
    except Exception as e:
        logging.error(f"Tag usage statistics test FAILED: {e}")
        return False

def test_classification_pattern_analysis():
    """Test tag classification pattern analysis."""
    logging.info("\n=== Testing Classification Pattern Analysis ===")
    
    try:
        analysis = analyze_tag_classification_patterns()
        
        logging.info(f"✓ Found {analysis['pattern_count']} strong tag patterns")
        logging.info(f"✓ Analyzed {len(analysis['category_analysis'])} categories")
        
        if analysis['strong_tag_patterns']:
            logging.info("Strong tag patterns:")
            for pattern in analysis['strong_tag_patterns'][:3]:  # Show top 3
                logging.info(f"  - {pattern['tag_category']}: {pattern['tag_value']} → {pattern['predicted_category']}")
                logging.info(f"    Accuracy: {pattern['accuracy']:.1%}, Sample size: {pattern['sample_size']}")
        
        if analysis['category_analysis']:
            logging.info("Category analysis:")
            for cat_analysis in analysis['category_analysis'][:3]:  # Show top 3
                logging.info(f"  - {cat_analysis['final_category']}: {cat_analysis['document_count']} docs, {cat_analysis['total_tags']} tags")
                logging.info(f"    Classification accuracy: {cat_analysis['classification_accuracy']:.1%}")
        
        logging.info("✅ Classification pattern analysis test PASSED")
        return True
        
    except Exception as e:
        logging.error(f"Classification pattern analysis test FAILED: {e}")
        return False

def test_database_constraints():
    """Test database constraints and edge cases."""
    logging.info("\n=== Testing Database Constraints ===")
    
    document_id, _ = create_test_document()
    if not document_id:
        logging.error("Failed to create test document")
        return False
    
    try:
        # Test duplicate tag handling
        duplicate_tags = {
            'people': ['John Smith', 'John Smith'],  # Duplicate value
            'organizations': ['ABC Company']
        }
        
        tags_stored = store_document_tags(document_id, duplicate_tags)
        retrieved_tags = get_document_tags(document_id)
        
        # Should only store unique values
        if len(retrieved_tags['people']) == 1 and 'John Smith' in retrieved_tags['people']:
            logging.info("✓ Duplicate tag values handled correctly")
        else:
            logging.error(f"Duplicate handling failed: {retrieved_tags['people']}")
            return False
        
        # Test empty tag categories
        empty_tags = {
            'people': [],
            'organizations': ['XYZ Corp'],
            'places': [''],  # Empty string
            'dates': None  # None value
        }
        
        tags_stored = store_document_tags(document_id, empty_tags)
        retrieved_tags = get_document_tags(document_id)
        
        # Should only store non-empty values
        if ('XYZ Corp' in retrieved_tags.get('organizations', []) and 
            len(retrieved_tags.get('people', [])) == 0 and
            len(retrieved_tags.get('places', [])) == 0):
            logging.info("✓ Empty tag values handled correctly")
        else:
            logging.error(f"Empty value handling failed: {retrieved_tags}")
            return False
        
        # Test invalid tag category (should be caught by CHECK constraint)
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO document_tags (document_id, tag_category, tag_value)
                VALUES (?, ?, ?)
            """, (document_id, 'invalid_category', 'test_value'))
            conn.commit()
            logging.error("Invalid category was accepted - constraint not working")
            return False
        except Exception:
            logging.info("✓ Invalid tag category correctly rejected")
        finally:
            conn.close()
        
        logging.info("✅ Database constraints test PASSED")
        return True
        
    except Exception as e:
        logging.error(f"Database constraints test FAILED: {e}")
        return False

def cleanup_test_data():
    """Clean up test data."""
    logging.info("\n=== Cleaning Up Test Data ===")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Delete test tags
        cursor.execute("DELETE FROM document_tags WHERE document_id IN (SELECT id FROM single_documents WHERE batch_id IN (SELECT id FROM batches WHERE status = 'testing'))")
        
        # Delete test documents
        cursor.execute("DELETE FROM single_documents WHERE batch_id IN (SELECT id FROM batches WHERE status = 'testing')")
        
        # Delete test batches
        cursor.execute("DELETE FROM batches WHERE status = 'testing'")
        
        conn.commit()
        logging.info("✓ Test data cleaned up successfully")
        
    except Exception as e:
        logging.error(f"Failed to clean up test data: {e}")
    finally:
        conn.close()

def main():
    """Run all tag database integration tests."""
    logging.info("🏷️  Starting Tag Database Integration Tests")
    logging.info("=" * 60)
    
    test_results = []
    
    # Run all tests
    test_results.append(("Tag Storage and Retrieval", test_tag_storage_and_retrieval()))
    test_results.append(("Similar Document Search", test_similar_document_search()))
    test_results.append(("Tag Usage Statistics", test_tag_usage_stats()))
    test_results.append(("Classification Pattern Analysis", test_classification_pattern_analysis()))
    test_results.append(("Database Constraints", test_database_constraints()))
    
    # Clean up
    cleanup_test_data()
    
    # Summary
    logging.info("\n" + "=" * 60)
    logging.info("🏷️  TAG DATABASE INTEGRATION TEST RESULTS")
    logging.info("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        logging.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logging.info("-" * 60)
    logging.info(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        logging.info("🎉 ALL TESTS PASSED - Tag database integration is working correctly!")
        return True
    else:
        logging.error(f"❌ {total - passed} tests failed - check implementation")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
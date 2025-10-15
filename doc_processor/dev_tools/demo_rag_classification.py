#!/usr/bin/env python3
"""
RAG-Enhanced Classification Demo

This script demonstrates how tag-based RAG can improve document classification
by using similar documents' tag patterns to provide context to the LLM.
"""

import sys
import os
import logging
from typing import Dict, List

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import find_similar_documents_by_tags, analyze_tag_classification_patterns
from llm_utils import extract_document_tags, _query_ollama
from config_manager import app_config

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def rag_enhanced_classification(document_text: str, document_name: str) -> Dict:
    """
    Classify a document using RAG-enhanced context from similar documents.

    Args:
        document_text (str): The OCR text of the document to classify
        document_name (str): Name of the document for logging

    Returns:
        dict: Classification result with RAG context and reasoning
    """
    logging.info(f"🤖 Starting RAG-enhanced classification for: {document_name}")

    try:
        # Step 1: Extract tags from the current document
        extracted_tags = extract_document_tags(document_text, document_name)

        if not extracted_tags:
            logging.warning("⚠️  No tags extracted - falling back to standard classification")
            return standard_classification(document_text, document_name)

        # Step 2: Find similar documents based on tag patterns
        similar_docs = find_similar_documents_by_tags(extracted_tags, limit=5, min_tag_matches=1)

        # Step 3: Build RAG context from similar documents
        rag_context = build_classification_context(similar_docs, extracted_tags)

        # Step 4: Get classification patterns for additional context
        classification_patterns = analyze_tag_classification_patterns()
        strong_patterns = classification_patterns.get('strong_tag_patterns', [])

        # Step 5: Enhanced classification with RAG context
        enhanced_result = classify_with_rag_context(
            document_text, document_name, extracted_tags, rag_context, strong_patterns
        )

        return enhanced_result

    except Exception as e:
        logging.error(f"💥 RAG-enhanced classification failed for {document_name}: {e}")
        return standard_classification(document_text, document_name)

def build_classification_context(similar_docs: List[Dict], current_tags: Dict) -> str:
    """Build human-readable context from similar documents."""

    if not similar_docs:
        return "No similar documents found in the database."

    context = f"Found {len(similar_docs)} similar documents based on tag patterns:\n\n"

    for i, doc in enumerate(similar_docs, 1):
        context += f"{i}. Document Category: {doc['final_category']}\n"
        context += f"   Matching Tags ({doc['tag_matches']} matches): {', '.join(doc['matching_tags'])}\n"
        context += f"   Tag Category: {doc['tag_category']}\n"

        # Show if AI was correct or corrected
        if doc['ai_suggested_category'] != doc['final_category']:
            context += f"   Note: AI suggested '{doc['ai_suggested_category']}' but human corrected to '{doc['final_category']}'\n"
        else:
            context += f"   Note: AI suggestion '{doc['ai_suggested_category']}' was confirmed by human\n"

        context += "\n"

    return context

def classify_with_rag_context(
    document_text: str,
    document_name: str,
    extracted_tags: Dict,
    rag_context: str,
    strong_patterns: List[Dict]
) -> Dict:
    """Classify document using RAG context."""

    # Build pattern context
    pattern_context = ""
    if strong_patterns:
        pattern_context = "Historical classification patterns (high accuracy):\n"
        for pattern in strong_patterns[:5]:  # Top 5 patterns
            pattern_context += f"- {pattern['tag_category']}: '{pattern['tag_value']}' → {pattern['predicted_category']} (accuracy: {pattern['accuracy']:.1%})\n"
        pattern_context += "\n"

    # Build current tags summary
    current_tags_summary = "Current document tags:\n"
    for category, values in extracted_tags.items():
        if values:
            current_tags_summary += f"- {category.replace('_', ' ').title()}: {', '.join(values)}\n"

    # Enhanced prompt with RAG context
    enhanced_prompt = f"""You are a document classification expert with access to historical data about how similar documents have been classified.

{pattern_context}

SIMILAR DOCUMENTS CONTEXT:
{rag_context}

{current_tags_summary}

DOCUMENT TO CLASSIFY:
{document_text[:2000]}

Based on the historical patterns and similar documents above, classify this document into one of these categories:
- Financial Document
- Legal Document
- Personal Correspondence
- Technical Document
- Medical Record
- Educational Material
- Receipt or Invoice
- Form or Application
- News Article or Publication
- Other

Provide your response in this JSON format:
{{
    "category": "your_classification",
    "confidence": 0.85,
    "reasoning": "explanation of why you chose this category, referencing the historical context",
    "rag_insights": "how the similar documents influenced your decision"
}}"""

    try:
        response = _query_ollama(
            enhanced_prompt,
            timeout=app_config.OLLAMA_TIMEOUT,
            context_window=app_config.OLLAMA_CONTEXT_WINDOW,
            task_name="rag_classification"
        )

        # Parse JSON response
        import json
        result = json.loads(response)

        # Add metadata
        result['method'] = 'rag_enhanced'
        result['similar_docs_found'] = len(rag_context.split('\n\n')) - 1 if rag_context else 0
        result['patterns_used'] = len(strong_patterns)

        logging.info(f"✅ RAG-enhanced classification complete for {document_name}")
        logging.info(f"🎯 Category: {result['category']} (confidence: {result['confidence']:.1%})")

        return result

    except json.JSONDecodeError as e:
        logging.error(f"💥 Failed to parse LLM response as JSON: {e}")
        return {"category": "Other", "confidence": 0.5, "reasoning": "Failed to parse LLM response", "method": "fallback"}
    except Exception as e:
        logging.error(f"💥 Enhanced classification failed: {e}")
        return {"category": "Other", "confidence": 0.5, "reasoning": str(e), "method": "error"}

def standard_classification(document_text: str, document_name: str) -> Dict:
    """Standard classification without RAG context."""

    prompt = f"""Classify this document into one of these categories:
- Financial Document
- Legal Document
- Personal Correspondence
- Technical Document
- Medical Record
- Educational Material
- Receipt or Invoice
- Form or Application
- News Article or Publication
- Other

Document: {document_text[:2000]}

Respond with JSON: {{"category": "your_classification", "confidence": 0.85, "reasoning": "brief explanation"}}"""

    try:
        response = _query_ollama(prompt, task_name="standard_classification")
        import json
        result = json.loads(response)
        result['method'] = 'standard'
        return result
    except:
        return {"category": "Other", "confidence": 0.5, "reasoning": "Classification failed", "method": "fallback"}

def demo_rag_classification():
    """Demonstrate RAG-enhanced classification with sample documents."""

    logging.info("🏷️  RAG-Enhanced Classification Demo")
    logging.info("=" * 60)

    # Sample documents to test
    test_documents = [
        {
            "name": "sample_invoice.pdf",
            "text": """
            INVOICE

            TechCorp Solutions Inc.
            456 Innovation Drive
            San Francisco, CA 94105

            Bill To:
            Johnson & Associates
            789 Business Blvd
            New York, NY 10001

            Invoice Number: INV-2024-001
            Date: March 15, 2024
            Due Date: April 15, 2024

            Description                 Quantity    Rate        Amount
            Software Development        40 hours    $150/hr     $6,000.00
            Project Management          10 hours    $120/hr     $1,200.00
            Testing & QA               15 hours    $100/hr     $1,500.00

            Subtotal:                                           $8,700.00
            Tax (8.5%):                                         $739.50
            Total:                                              $9,439.50

            Payment Terms: Net 30 days
            Thank you for your business!
            """
        },
        {
            "name": "contract_sample.pdf",
            "text": """
            SERVICE AGREEMENT

            This Service Agreement ("Agreement") is entered into on April 1, 2024,
            between TechCorp Solutions Inc., a corporation organized under the laws
            of California ("Provider"), and Johnson & Associates LLC ("Client").

            1. SCOPE OF SERVICES
            Provider agrees to deliver software development services including:
            - Custom application development
            - Database design and implementation
            - User interface design
            - Quality assurance testing

            2. COMPENSATION
            Client agrees to pay Provider $150 per hour for development work,
            $120 per hour for project management, and $100 per hour for testing.

            3. TERM
            This Agreement shall commence on April 1, 2024 and continue until
            project completion, estimated at 6 months.

            4. CONFIDENTIALITY
            Both parties agree to maintain strict confidentiality of all
            proprietary information shared during this engagement.

            IN WITNESS WHEREOF, the parties have executed this Agreement.

            TechCorp Solutions Inc.           Johnson & Associates LLC
            _____________________            _____________________
            Sarah Johnson, CEO               Michael Johnson, Partner
            Date: _______________            Date: _______________
            """
        }
    ]

    for doc in test_documents:
        logging.info(f"\n--- Testing Document: {doc['name']} ---")

        # Get RAG-enhanced classification
        result = rag_enhanced_classification(doc['text'], doc['name'])

        logging.info("📋 Classification Result:")
        logging.info(f"   Category: {result.get('category', 'Unknown')}")
        logging.info(f"   Confidence: {result.get('confidence', 0):.1%}")
        logging.info(f"   Method: {result.get('method', 'unknown')}")
        logging.info(f"   Similar docs used: {result.get('similar_docs_found', 0)}")
        logging.info(f"   Patterns used: {result.get('patterns_used', 0)}")
        logging.info(f"   Reasoning: {result.get('reasoning', 'No reasoning provided')}")

        if 'rag_insights' in result:
            logging.info(f"   RAG Insights: {result['rag_insights']}")

def main():
    """Run the RAG classification demo."""
    try:
        demo_rag_classification()
        logging.info("\n🎉 RAG-Enhanced Classification Demo Complete!")

    except Exception as e:
        logging.error(f"💥 Demo failed: {e}")
        import traceback
        logging.debug(traceback.format_exc())

if __name__ == "__main__":
    main()
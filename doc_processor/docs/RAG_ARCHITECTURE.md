# RAG (Retrieval-Augmented Generation) Architecture Plan

**Document Processing System Enhancement with Learning Capabilities**

## Overview

This document outlines the architectural plan for implementing RAG (Retrieval-Augmented Generation) capabilities in our document processing system. RAG will enable the LLM to learn from historical human decisions and corrections, making increasingly intelligent suggestions over time.

## What is RAG?

RAG combines:
1. **Retrieval**: Search through stored knowledge/data 
2. **Augmented**: Enhance LLM prompts with retrieved context
3. **Generation**: LLM makes decisions using both its training + your specific data

## Current Data Assets (RAG Gold Mine)

Our system already collects perfect RAG data:

```sql
-- Rich data sources we already have:
interaction_log     -- Every human correction/decision with timestamps
single_documents    -- OCR text + AI classifications + human finals
pages              -- Page-level text + categories + confidence scores
categories         -- Custom categories + usage patterns + evolution
category_change_log -- Category evolution over time + rename history
batches            -- Batch-level processing patterns and outcomes
```

## RAG Architecture Options

### Option 1: Simple SQL-Based RAG (Recommended Start)

**Advantages:**
- Uses existing SQLite database
- No additional dependencies
- Fast to implement
- Leverages existing data structure

**Implementation:**
```python
# When LLM needs to classify a document:
def get_classification_context(ocr_text, doc_type):
    # Find similar documents that humans corrected
    similar_docs = db.execute("""
        SELECT ai_suggested_category, final_category, confidence_score
        FROM single_documents 
        WHERE ocr_text LIKE ? 
        AND final_category != ai_suggested_category
        LIMIT 5
    """, [f"%{key_words}%"])
    
    # Build enhanced prompt
    context = f"""
    Previous human corrections for similar documents:
    {format_corrections(similar_docs)}
    
    Current document: {ocr_text}
    Classify this document...
    """
```

### Option 2: Vector Embeddings RAG (Advanced)

**Advantages:**
- Semantic similarity (not just keyword matching)
- More sophisticated document retrieval
- Better handling of similar content with different wording

**Implementation:**
```python
# Store document embeddings for semantic search
from sentence_transformers import SentenceTransformer

class RAGSystem:
    def __init__(self):
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.vector_store = {}  # or Chroma/FAISS
    
    def add_document(self, doc_id, text, human_decision):
        embedding = self.embedder.encode(text)
        self.vector_store[doc_id] = {
            'embedding': embedding,
            'text': text, 
            'human_decision': human_decision
        }
    
    def find_similar(self, query_text, k=5):
        query_embedding = self.embedder.encode(query_text)
        return self.search_vectors(query_embedding, k)
```

## Implementation Roadmap

### Phase 1: Basic RAG Foundation (2-3 weeks)

**Goal:** Add simple context retrieval to enhance LLM decisions

#### 1.1 Create RAG Data Layer
```python
# doc_processor/rag_system.py
class SimpleRAG:
    def __init__(self, db_connection):
        self.db = db_connection
    
    def get_classification_hints(self, ocr_text):
        """Find documents with human corrections similar to current text"""
        corrections = self.find_human_corrections(ocr_text)
        return self.format_context(corrections)
    
    def get_category_usage_patterns(self):
        """Get most used categories, recent additions, trending patterns"""
        return self.get_category_stats()
    
    def get_filename_examples(self, category):
        """Show examples of successful filenames in this category"""
        return self.get_naming_patterns(category)
    
    def find_human_corrections(self, ocr_text):
        """SQL-based similarity search for human corrections"""
        # Extract key terms from OCR text
        key_terms = self.extract_key_terms(ocr_text)
        
        corrections = []
        for term in key_terms:
            results = self.db.execute("""
                SELECT ai_suggested_category, final_category, 
                       final_filename, ocr_text, confidence_score
                FROM single_documents 
                WHERE (ai_suggested_category != final_category 
                       OR ai_suggested_filename != final_filename)
                AND ocr_text LIKE ?
                ORDER BY created_at DESC
                LIMIT 3
            """, [f"%{term}%"])
            corrections.extend(results)
        
        return self.deduplicate_corrections(corrections)
```

#### 1.2 Enhance Existing LLM Calls
```python
# In processing.py, modify get_ai_classification():
def get_ai_classification(page_text):
    # Initialize RAG system
    rag = SimpleRAG(get_db_connection())
    
    # Get context from historical data
    classification_hints = rag.get_classification_hints(page_text)
    category_patterns = rag.get_category_usage_patterns()
    
    # Build enhanced prompt
    enhanced_prompt = f"""
    HISTORICAL CONTEXT:
    {classification_hints}
    
    CATEGORY USAGE PATTERNS:
    {category_patterns}
    
    CURRENT DOCUMENT TO CLASSIFY:
    {page_text}
    
    Based on the historical patterns and human corrections above, 
    what category best fits this document?
    """
    
    return call_ollama(enhanced_prompt)
```

#### 1.3 Integration Points
- **Document Classification**: Enhance category suggestions
- **Filename Generation**: Show examples of good filenames
- **Confidence Scoring**: Use historical accuracy to adjust confidence

### Phase 2: Smart Learning Engine (4-6 weeks)

**Goal:** Implement pattern recognition and systematic error detection

#### 2.1 Pattern Recognition
```python
class LearningEngine:
    def analyze_correction_patterns(self):
        """Identify systematic misclassifications"""
        patterns = self.db.execute("""
            SELECT ai_suggested_category, final_category, 
                   COUNT(*) as frequency,
                   AVG(confidence_score) as avg_confidence
            FROM single_documents 
            WHERE ai_suggested_category != final_category
            GROUP BY ai_suggested_category, final_category
            HAVING COUNT(*) >= 3
            ORDER BY frequency DESC
        """)
        
        insights = []
        for pattern in patterns:
            insight = f"AI consistently misclassifies {pattern['ai_suggested_category']} as {pattern['final_category']} ({pattern['frequency']} times)"
            insights.append(insight)
        
        return insights
    
    def suggest_category_improvements(self):
        """Analyze category usage and suggest improvements"""
        # Find categories that are never used
        unused = self.find_unused_categories()
        
        # Find categories that are frequently corrected to the same thing
        merge_candidates = self.find_merge_candidates()
        
        # Find documents that don't fit existing categories well
        new_category_candidates = self.find_new_category_patterns()
        
        return {
            "unused_categories": unused,
            "merge_suggestions": merge_candidates,
            "new_category_suggestions": new_category_candidates
        }
```

#### 2.2 Enhanced Confidence Scoring
```python
def enhanced_classification_with_confidence(text):
    # Get AI classification
    ai_result = get_ai_classification(text)
    
    # Calculate confidence based on historical accuracy
    historical_accuracy = calculate_historical_accuracy(text, ai_result)
    content_similarity = find_content_similarity_confidence(text)
    
    final_confidence = combine_confidence_scores(
        ai_result.confidence, 
        historical_accuracy, 
        content_similarity
    )
    
    # Auto-flag for review if confidence is low
    if final_confidence < 0.7:
        return {
            "category": ai_result.category,
            "filename": ai_result.filename,
            "confidence": final_confidence,
            "flag_for_review": True,
            "reason": "Low confidence based on historical patterns"
        }
    
    return {
        "category": ai_result.category,
        "filename": ai_result.filename,
        "confidence": final_confidence,
        "flag_for_review": False
    }
```

### Phase 3: Advanced RAG with Vector Embeddings (6-8 weeks)

**Goal:** Implement semantic search and multi-stage RAG integration

#### 3.1 Vector Embeddings Implementation
```python
class VectorRAG:
    def __init__(self):
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.vector_db = self.initialize_vector_store()
    
    def add_document_to_vector_store(self, doc_id, text, metadata):
        """Add document embedding to vector store"""
        embedding = self.embedder.encode(text)
        self.vector_db.add(
            ids=[str(doc_id)],
            embeddings=[embedding.tolist()],
            metadatas=[metadata],
            documents=[text]
        )
    
    def find_semantic_matches(self, query_text, k=5):
        """Find semantically similar documents"""
        query_embedding = self.embedder.encode(query_text)
        results = self.vector_db.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=k,
            include=['metadatas', 'documents', 'distances']
        )
        return self.format_semantic_results(results)
```

#### 3.2 Multi-Stage RAG Integration
```python
class WorkflowRAG:
    """Different RAG strategies for different workflow stages"""
    
    def verification_rag(self, page_text):
        """RAG context for verification stage"""
        return {
            "common_corrections": self.get_verification_patterns(),
            "similar_pages": self.find_similar_verified_pages(page_text),
            "confidence_indicators": self.get_confidence_patterns()
        }
    
    def grouping_rag(self, pages):
        """RAG context for document grouping"""
        return {
            "grouping_patterns": self.get_historical_groupings(pages),
            "document_types": self.identify_document_types(pages),
            "naming_suggestions": self.get_document_naming_patterns()
        }
    
    def ordering_rag(self, document_pages):
        """RAG context for page ordering"""
        return {
            "typical_orders": self.get_page_ordering_patterns(),
            "content_flow": self.analyze_content_flow(document_pages),
            "document_structure": self.identify_document_structure()
        }
    
    def naming_rag(self, category, content):
        """RAG context for filename generation"""
        return {
            "naming_patterns": self.get_category_naming_patterns(category),
            "successful_examples": self.get_highly_rated_filenames(category),
            "content_keywords": self.extract_naming_keywords(content)
        }
```

## Specific Implementation Areas

### 1. Smart Classification Enhancement
```python
def rag_enhanced_classification(ocr_text):
    """Classification with RAG context"""
    
    # Find similar documents where humans made corrections
    human_wisdom = db.execute("""
        SELECT ai_suggested_category, final_category, 
               final_filename, ocr_text,
               COUNT(*) as correction_frequency,
               AVG(confidence_score) as avg_confidence
        FROM single_documents 
        WHERE ai_suggested_category != final_category
        AND similarity_score(?, ocr_text) > 0.6
        GROUP BY ai_suggested_category, final_category
        ORDER BY correction_frequency DESC, avg_confidence DESC
        LIMIT 5
    """, [ocr_text])
    
    # Build correction context
    correction_context = build_correction_context(human_wisdom)
    
    # Get recent category trends
    category_trends = get_recent_category_usage()
    
    # Enhanced prompt with context
    enhanced_prompt = f"""
    HUMAN CORRECTION PATTERNS:
    {correction_context}
    
    RECENT CATEGORY TRENDS:
    {category_trends}
    
    DOCUMENT TO CLASSIFY:
    {ocr_text}
    
    Based on the correction patterns above, classify this document.
    Pay special attention to patterns where humans consistently 
    corrected similar documents.
    """
    
    return enhanced_llm_call(enhanced_prompt)
```

### 2. Intelligent Filename Generation
```python
def rag_filename_generation(category, ocr_text):
    """Generate filenames using successful patterns"""
    
    # Get successful filename examples in this category
    examples = db.execute("""
        SELECT final_filename, ocr_text, 
               (CASE WHEN user_rating IS NOT NULL THEN user_rating ELSE 3 END) as rating
        FROM single_documents 
        WHERE final_category = ?
        AND final_filename IS NOT NULL
        AND final_filename != ai_suggested_filename
        ORDER BY rating DESC, created_at DESC
        LIMIT 10
    """, [category])
    
    # Build filename pattern context
    pattern_context = build_filename_patterns(examples)
    
    prompt = f"""
    SUCCESSFUL FILENAME PATTERNS FOR {category.upper()}:
    {pattern_context}
    
    DOCUMENT CONTENT:
    {ocr_text}
    
    Generate a filename following the successful patterns above.
    Focus on the most important identifying information from the content.
    """
    
    return generate_filename(prompt)
```

### 3. Category Evolution and Suggestions
```python
def analyze_category_evolution():
    """Suggest category improvements based on usage patterns"""
    
    # Find categories that are frequently corrected
    problem_categories = db.execute("""
        SELECT ai_suggested_category, 
               COUNT(*) as total_suggestions,
               COUNT(CASE WHEN ai_suggested_category != final_category THEN 1 END) as corrections,
               (COUNT(CASE WHEN ai_suggested_category != final_category THEN 1 END) * 100.0 / COUNT(*)) as error_rate
        FROM single_documents 
        WHERE ai_suggested_category IS NOT NULL
        GROUP BY ai_suggested_category
        HAVING error_rate > 30
        ORDER BY error_rate DESC
    """)
    
    # Find emerging category patterns
    emerging_patterns = db.execute("""
        SELECT final_category, COUNT(*) as frequency,
               GROUP_CONCAT(DISTINCT ai_suggested_category) as ai_suggestions
        FROM single_documents 
        WHERE final_category NOT IN (SELECT name FROM categories WHERE is_default = 1)
        AND created_at > date('now', '-30 days')
        GROUP BY final_category
        HAVING frequency >= 5
        ORDER BY frequency DESC
    """)
    
    return {
        "problematic_categories": problem_categories,
        "emerging_categories": emerging_patterns,
        "recommendations": generate_category_recommendations(problem_categories, emerging_patterns)
    }
```

## Database Schema Extensions

### New Tables for RAG Support
```sql
-- Store document embeddings for semantic search
CREATE TABLE document_embeddings (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES single_documents(id),
    embedding_model TEXT DEFAULT 'all-MiniLM-L6-v2',
    embedding BLOB,  -- Store vector embeddings as binary data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, embedding_model)
);

-- Store RAG insights and learning patterns
CREATE TABLE rag_insights (
    id INTEGER PRIMARY KEY,
    insight_type TEXT CHECK(insight_type IN ('correction_pattern', 'category_suggestion', 'filename_pattern', 'confidence_adjustment')),
    category TEXT,
    pattern_data JSON,  -- Store structured pattern information
    confidence_score REAL CHECK(confidence_score BETWEEN 0 AND 1),
    usage_count INTEGER DEFAULT 0,
    success_rate REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

-- Track RAG-enhanced predictions and their outcomes
CREATE TABLE rag_predictions (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES single_documents(id),
    prediction_type TEXT CHECK(prediction_type IN ('category', 'filename', 'confidence')),
    rag_context JSON,  -- Store the context used for prediction
    ai_prediction TEXT,
    rag_enhanced_prediction TEXT,
    human_final_decision TEXT,
    prediction_accuracy REAL,
    rag_improvement REAL,  -- How much RAG improved the prediction
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Enhanced Views for Analysis
```sql
-- View for analyzing correction patterns
CREATE VIEW corrections_analysis AS
SELECT 
    ai_suggested_category,
    final_category,
    COUNT(*) as frequency,
    AVG(confidence_score) as avg_confidence,
    MIN(created_at) as first_occurrence,
    MAX(created_at) as last_occurrence,
    (COUNT(*) * 100.0 / (SELECT COUNT(*) FROM single_documents WHERE ai_suggested_category = s.ai_suggested_category)) as correction_rate
FROM single_documents s
WHERE ai_suggested_category != final_category
AND ai_suggested_category IS NOT NULL
AND final_category IS NOT NULL
GROUP BY ai_suggested_category, final_category
ORDER BY frequency DESC;

-- View for category usage trends
CREATE VIEW category_usage_trends AS
SELECT 
    final_category,
    COUNT(*) as usage_count,
    AVG(confidence_score) as avg_confidence,
    COUNT(CASE WHEN ai_suggested_category = final_category THEN 1 END) as ai_correct_count,
    COUNT(CASE WHEN ai_suggested_category != final_category THEN 1 END) as ai_incorrect_count,
    date(created_at) as usage_date
FROM single_documents
WHERE final_category IS NOT NULL
GROUP BY final_category, date(created_at)
ORDER BY usage_date DESC, usage_count DESC;

-- View for filename pattern analysis
CREATE VIEW filename_patterns AS
SELECT 
    final_category,
    final_filename,
    LENGTH(final_filename) as filename_length,
    (final_filename LIKE '%-%') as has_dashes,
    (final_filename LIKE '%_%') as has_underscores,
    (final_filename LIKE '% %') as has_spaces,
    (final_filename LIKE '%[0-9][0-9][0-9][0-9]%') as has_year,
    ocr_text,
    created_at
FROM single_documents
WHERE final_filename IS NOT NULL
AND final_category IS NOT NULL;
```

## Performance Considerations

### Optimization Strategies
1. **Index Creation**: Add indexes for frequently queried columns
2. **Query Optimization**: Use prepared statements and efficient JOINs
3. **Caching**: Cache frequently accessed RAG contexts
4. **Lazy Loading**: Load embeddings only when needed
5. **Batch Processing**: Process multiple documents together when possible

### Monitoring and Metrics
```python
class RAGMetrics:
    def track_rag_effectiveness(self):
        """Monitor how RAG improves predictions"""
        return {
            "accuracy_improvement": self.calculate_accuracy_improvement(),
            "confidence_calibration": self.check_confidence_calibration(),
            "context_relevance": self.measure_context_relevance(),
            "performance_impact": self.measure_performance_impact()
        }
    
    def generate_rag_report(self):
        """Generate comprehensive RAG performance report"""
        return {
            "total_rag_enhanced_predictions": self.count_rag_predictions(),
            "accuracy_by_category": self.accuracy_by_category(),
            "most_valuable_contexts": self.identify_valuable_contexts(),
            "improvement_opportunities": self.find_improvement_areas()
        }
```

## Integration Timeline

### Immediate (Phase 1): 2-3 weeks
- [ ] Create `rag_system.py` module
- [ ] Implement simple SQL-based context retrieval
- [ ] Enhance document classification with basic RAG
- [ ] Add correction pattern analysis
- [ ] Create basic confidence scoring adjustments

### Short-term (Phase 2): 4-6 weeks
- [ ] Implement learning engine for pattern recognition
- [ ] Add category evolution analysis
- [ ] Enhance filename generation with RAG
- [ ] Create systematic error detection
- [ ] Add RAG effectiveness monitoring

### Medium-term (Phase 3): 6-8 weeks
- [ ] Implement vector embeddings with sentence transformers
- [ ] Add semantic similarity search
- [ ] Create multi-stage RAG for different workflow phases
- [ ] Implement advanced confidence calibration
- [ ] Add automated category suggestions

### Long-term (Future): 8+ weeks
- [ ] Integration with external knowledge bases
- [ ] Advanced machine learning for pattern recognition
- [ ] Real-time learning and adaptation
- [ ] Cross-batch learning and optimization
- [ ] API for external RAG data sources

## Success Metrics

### Quantitative Metrics
- **Classification Accuracy**: Improvement in AI category suggestions
- **Filename Quality**: Reduction in filename corrections
- **Confidence Calibration**: Better correlation between confidence and accuracy
- **Processing Efficiency**: Reduction in human review time
- **Pattern Recognition**: Number of useful patterns discovered

### Qualitative Metrics
- **User Satisfaction**: Reduced frustration with AI suggestions
- **Workflow Efficiency**: Smoother verification and review processes
- **System Intelligence**: Noticeable improvement in AI suggestions over time
- **Category Evolution**: More intuitive and useful category structures

## Conclusion

This RAG implementation will transform our document processing system from a static AI classifier into an intelligent, learning system that continuously improves based on human feedback. The phased approach ensures we can deliver value incrementally while building towards a sophisticated learning architecture.

The key advantage is leveraging the rich data we're already collecting - every human correction, category change, and workflow decision becomes training data for making the system smarter over time.

---

**Next Steps:**
1. Review and approve this architectural plan
2. Begin Phase 1 implementation with simple SQL-based RAG
3. Set up monitoring and metrics collection
4. Plan integration points with existing workflow
5. Establish success criteria and evaluation methods
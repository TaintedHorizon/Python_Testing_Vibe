# Tag Extraction RAG Integration Plan

## Overview
This document outlines how the tag extraction feature integrates with the planned RAG architecture to create an intelligent, learning document processing system.

## Current Tag Extraction Capabilities

### Tag Categories Extracted
- **people**: Individual names mentioned in documents
- **organizations**: Companies, institutions, agencies
- **places**: Locations, addresses, geographic references
- **dates**: Temporal references in various formats
- **document_types**: Document classification (invoice, contract, etc.)
- **keywords**: Subject matter and industry terms
- **amounts**: Monetary values and quantities
- **reference_numbers**: Account numbers, IDs, case numbers

### Storage Strategy
**Current**: Tags stored in exported markdown files as structured sections
**RAG Future**: Tags will be indexed in database for retrieval and learning

## RAG Integration Phases

### Phase 1: Tag-Enhanced Context Retrieval (Immediate)

#### 1.1 Database Schema Extension
```sql
-- Add tags table for structured storage and indexing
CREATE TABLE document_tags (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES single_documents(id),
    tag_category TEXT CHECK(tag_category IN ('people', 'organizations', 'places', 'dates', 'document_types', 'keywords', 'amounts', 'reference_numbers')),
    tag_value TEXT NOT NULL,
    extraction_confidence REAL,
    llm_source TEXT, -- Which LLM extracted this tag
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, tag_category, tag_value)
);

-- Index for fast tag-based retrieval
CREATE INDEX idx_document_tags_category_value ON document_tags(tag_category, tag_value);
CREATE INDEX idx_document_tags_document_id ON document_tags(document_id);
```

#### 1.2 Tag-Based Document Retrieval
```python
def find_similar_documents_by_tags(extracted_tags, limit=5):
    """
    Find documents with similar tag patterns for RAG context
    """
    similar_docs = []
    
    for category, values in extracted_tags.items():
        if not values:
            continue
            
        # Find documents with matching tags in this category
        matches = db.execute("""
            SELECT DISTINCT d.id, d.final_category, d.final_filename, d.ocr_text,
                   COUNT(t.tag_value) as tag_matches
            FROM single_documents d
            JOIN document_tags t ON d.id = t.document_id
            WHERE t.tag_category = ? AND t.tag_value IN ({})
            GROUP BY d.id
            HAVING tag_matches >= 2
            ORDER BY tag_matches DESC, d.created_at DESC
            LIMIT ?
        """.format(','.join(['?' for _ in values])), 
        [category] + values + [limit])
        
        similar_docs.extend(matches)
    
    return deduplicate_by_relevance(similar_docs)

def rag_enhanced_classification_with_tags(ocr_text):
    """
    Use tag-based similarity for classification context
    """
    # Extract tags from current document
    current_tags = extract_document_tags(ocr_text, "temp_document")
    
    if current_tags:
        # Find similar documents by tag patterns
        similar_docs = find_similar_documents_by_tags(current_tags)
        
        # Build RAG context
        tag_context = build_tag_similarity_context(similar_docs, current_tags)
        
        # Enhanced prompt with tag-based context
        enhanced_prompt = f"""
        SIMILAR DOCUMENTS BY TAG PATTERNS:
        {tag_context}
        
        CURRENT DOCUMENT TAGS:
        {format_tags_for_prompt(current_tags)}
        
        DOCUMENT TEXT TO CLASSIFY:
        {ocr_text}
        
        Based on the tag similarities above, what category best fits this document?
        """
        
        return enhanced_llm_classification(enhanced_prompt)
    
    # Fallback to standard classification
    return get_ai_classification(ocr_text)
```

#### 1.3 Tag Pattern Learning
```python
def analyze_tag_classification_patterns():
    """
    Learn which tag patterns predict which categories
    """
    patterns = db.execute("""
        SELECT 
            d.final_category,
            t.tag_category,
            t.tag_value,
            COUNT(*) as frequency,
            COUNT(CASE WHEN d.ai_suggested_category = d.final_category THEN 1 END) as ai_correct,
            COUNT(CASE WHEN d.ai_suggested_category != d.final_category THEN 1 END) as ai_incorrect
        FROM single_documents d
        JOIN document_tags t ON d.id = t.document_id
        WHERE d.final_category IS NOT NULL
        GROUP BY d.final_category, t.tag_category, t.tag_value
        HAVING frequency >= 3
        ORDER BY frequency DESC
    """)
    
    # Identify strong tag-to-category correlations
    strong_patterns = []
    for pattern in patterns:
        accuracy = pattern['ai_correct'] / (pattern['ai_correct'] + pattern['ai_incorrect'])
        if accuracy > 0.8 and pattern['frequency'] >= 5:
            strong_patterns.append({
                'tag_category': pattern['tag_category'],
                'tag_value': pattern['tag_value'],
                'predicted_category': pattern['final_category'],
                'confidence': accuracy,
                'sample_size': pattern['frequency']
            })
    
    return strong_patterns
```

### Phase 2: Tag-Enhanced Filename Generation (2-4 weeks)

#### 2.1 Tag-Based Naming Patterns
```python
def rag_filename_generation_with_tags(category, extracted_tags, ocr_text):
    """
    Generate filenames using tag patterns from successful examples
    """
    # Find successful filenames in this category with similar tags
    naming_examples = db.execute("""
        SELECT d.final_filename, GROUP_CONCAT(t.tag_value) as tags
        FROM single_documents d
        JOIN document_tags t ON d.id = t.document_id
        WHERE d.final_category = ?
        AND d.final_filename IS NOT NULL
        AND d.final_filename != d.ai_suggested_filename
        AND t.tag_category IN ('organizations', 'dates', 'amounts', 'reference_numbers')
        GROUP BY d.id, d.final_filename
        ORDER BY d.created_at DESC
        LIMIT 10
    """, [category])
    
    # Analyze naming patterns from examples
    patterns = analyze_naming_patterns(naming_examples)
    
    # Build filename using tag data and patterns
    prompt = f"""
    SUCCESSFUL FILENAME PATTERNS FOR {category}:
    {format_naming_patterns(patterns)}
    
    EXTRACTED TAGS FOR CURRENT DOCUMENT:
    Organizations: {extracted_tags.get('organizations', [])}
    Dates: {extracted_tags.get('dates', [])}
    Amounts: {extracted_tags.get('amounts', [])}
    Reference Numbers: {extracted_tags.get('reference_numbers', [])}
    Document Types: {extracted_tags.get('document_types', [])}
    
    Generate a filename using the most relevant tags following the successful patterns.
    Focus on tags that uniquely identify this document.
    """
    
    return generate_filename_with_tags(prompt)
```

#### 2.2 Tag Quality Feedback Loop
```python
def record_tag_accuracy_feedback():
    """
    Track how well extracted tags correlate with final classifications
    """
    # When a document is finalized, analyze tag accuracy
    def on_document_finalized(document_id, final_category, final_filename):
        # Get the extracted tags for this document
        extracted_tags = get_document_tags(document_id)
        
        # Analyze if tags predicted the correct category
        tag_prediction_accuracy = evaluate_tag_category_prediction(extracted_tags, final_category)
        
        # Analyze if tags influenced filename quality  
        filename_tag_usage = evaluate_filename_tag_usage(extracted_tags, final_filename)
        
        # Store feedback for RAG learning
        db.execute("""
            INSERT INTO rag_insights (insight_type, category, pattern_data, confidence_score, created_at)
            VALUES ('tag_accuracy_feedback', ?, ?, ?, ?)
        """, [
            final_category,
            json.dumps({
                'document_id': document_id,
                'extracted_tags': extracted_tags,
                'category_prediction_accuracy': tag_prediction_accuracy,
                'filename_relevance': filename_tag_usage
            }),
            tag_prediction_accuracy,
            datetime.now()
        ])
```

### Phase 3: Advanced Tag-Based RAG (4-6 weeks)

#### 3.1 Semantic Tag Similarity
```python
class TagEmbeddingRAG:
    """
    Use embeddings for semantic tag similarity beyond exact matches
    """
    def __init__(self):
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.tag_embeddings = {}
    
    def embed_tag_values(self):
        """Create embeddings for all unique tag values"""
        unique_tags = db.execute("""
            SELECT DISTINCT tag_category, tag_value 
            FROM document_tags
        """)
        
        for tag in unique_tags:
            key = f"{tag['tag_category']}:{tag['tag_value']}"
            embedding = self.embedder.encode(tag['tag_value'])
            self.tag_embeddings[key] = embedding
    
    def find_semantically_similar_tags(self, tag_category, tag_value, threshold=0.7):
        """Find tags with similar semantic meaning"""
        query_embedding = self.embedder.encode(tag_value)
        similar_tags = []
        
        for key, embedding in self.tag_embeddings.items():
            if key.startswith(f"{tag_category}:"):
                similarity = cosine_similarity([query_embedding], [embedding])[0][0]
                if similarity > threshold:
                    tag_val = key.split(':', 1)[1]
                    similar_tags.append((tag_val, similarity))
        
        return sorted(similar_tags, key=lambda x: x[1], reverse=True)
```

#### 3.2 Cross-Document Tag Analysis
```python
def analyze_cross_document_tag_patterns():
    """
    Identify patterns across related documents in batches
    """
    batch_patterns = db.execute("""
        SELECT 
            b.id as batch_id,
            d.final_category,
            t.tag_category,
            t.tag_value,
            COUNT(DISTINCT d.id) as documents_with_tag,
            COUNT(d.id) as total_batch_documents
        FROM batches b
        JOIN single_documents d ON b.id = d.batch_id
        JOIN document_tags t ON d.id = t.document_id
        WHERE b.status = 'completed'
        GROUP BY b.id, d.final_category, t.tag_category, t.tag_value
        HAVING documents_with_tag >= 2
        ORDER BY batch_id, documents_with_tag DESC
    """)
    
    # Identify recurring tag patterns within batches
    batch_insights = {}
    for pattern in batch_patterns:
        batch_id = pattern['batch_id']
        if batch_id not in batch_insights:
            batch_insights[batch_id] = []
        
        if pattern['documents_with_tag'] / pattern['total_batch_documents'] > 0.5:
            batch_insights[batch_id].append({
                'dominant_tag': f"{pattern['tag_category']}:{pattern['tag_value']}",
                'category': pattern['final_category'],
                'coverage': pattern['documents_with_tag'] / pattern['total_batch_documents']
            })
    
    return batch_insights
```

## Implementation Integration Points

### 1. Modify `export_document()` in processing.py
- Add tag storage to database after markdown export
- Implement feedback collection on tag accuracy
- Create tag-based similarity search for classification context

### 2. Enhance `extract_document_tags()` in llm_utils.py  
- Add database storage capability
- Implement tag confidence scoring
- Add semantic validation against existing tag patterns

### 3. Create new `rag_tags.py` module
- Implement tag-based document retrieval
- Create tag pattern analysis functions
- Add tag-enhanced classification and naming

### 4. Extend database schema
- Add `document_tags` table for structured tag storage
- Create indexes for efficient tag-based queries
- Add RAG feedback tracking for tag accuracy

## Performance Considerations

### Tag Storage Strategy
- **Current**: Tags in markdown (human-readable, export-ready)
- **RAG Addition**: Tags in database (searchable, analyzable)
- **Hybrid**: Both approaches for different use cases

### Query Optimization
- Index tag_category and tag_value for fast lookups
- Use prepared statements for frequent tag queries
- Cache tag patterns for common categories

### Memory Management
- Lazy load tag embeddings only when needed
- Batch process tag similarity calculations
- Limit tag pattern cache size

## Success Metrics

### Quantitative
- **Classification Accuracy**: Improvement with tag-based RAG context
- **Filename Relevance**: Better tag usage in generated filenames  
- **Processing Speed**: Minimal impact on export performance
- **Tag Accuracy**: Correlation between extracted tags and final categories

### Qualitative  
- **User Experience**: More relevant AI suggestions
- **System Intelligence**: Learning from tag patterns over time
- **Export Quality**: Enhanced markdown with useful tag metadata

## Next Steps

1. **Immediate (This Week)**:
   - ✅ Tag extraction implementation (COMPLETED)
   - ✅ Verbose logging compliance (COMPLETED)
   - 🔄 Database schema design for tag storage

2. **Short-term (Next 2 weeks)**:
   - Implement `document_tags` table and storage
   - Add tag-based similarity search
   - Create basic RAG context retrieval using tags

3. **Medium-term (2-4 weeks)**:
   - Implement tag-enhanced classification
   - Add tag-based filename generation patterns
   - Create tag accuracy feedback loop

4. **Long-term (4-6 weeks)**:
   - Implement semantic tag similarity with embeddings
   - Add cross-document tag pattern analysis
   - Create advanced tag-based RAG features

---

**Status**: Tag extraction is fully implemented and RAG-ready. The feature follows established logging patterns and provides a strong foundation for the planned RAG architecture implementation.
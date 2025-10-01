#!/usr/bin/env python3
"""
Diagnostic tool to investigate OCR anomalies:
- Documents with high confidence but no OCR text
- Documents with suspicious confidence patterns
- Potential bugs in OCR processing/storage
"""

import sys
import os
import sqlite3
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def investigate_ocr_anomalies():
    """Investigate suspicious OCR patterns in the database"""
    
    db_path = Path(__file__).parent.parent / "documents.db"
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
        
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    print("🔍 OCR Anomaly Investigation Report")
    print("=" * 50)
    
    # Find documents with high confidence but no text
    print("\n1. High Confidence + No OCR Text (Suspicious):")
    cursor.execute("""
        SELECT id, batch_id, original_filename, ocr_confidence_avg, 
               LENGTH(ocr_text) as text_length,
               ai_suggested_category, ai_confidence
        FROM single_documents 
        WHERE ocr_confidence_avg > 90 AND (ocr_text IS NULL OR ocr_text = '')
        ORDER BY ocr_confidence_avg DESC
    """)
    
    suspicious_docs = cursor.fetchall()
    if suspicious_docs:
        for doc in suspicious_docs:
            print(f"  📄 ID:{doc[0]} Batch:{doc[1]} | {doc[2]}")
            print(f"     OCR Confidence: {doc[3]}% | Text Length: {doc[4] or 0}")
            print(f"     AI: {doc[5]} (conf: {doc[6]})")
            print()
    else:
        print("  ✅ No suspicious high-confidence + no-text documents found")
    
    # Find documents with exact 95.0 confidence (suspicious default?)
    print("\n2. Exact 95.0% Confidence (Potential Default Value):")
    cursor.execute("""
        SELECT id, batch_id, original_filename, ocr_confidence_avg,
               LENGTH(ocr_text) as text_length, 
               CASE WHEN ocr_text IS NULL THEN 'NULL' 
                    WHEN ocr_text = '' THEN 'EMPTY'
                    ELSE 'HAS_TEXT' END as text_status
        FROM single_documents 
        WHERE ocr_confidence_avg = 95.0
        ORDER BY id
    """)
    
    exact_95_docs = cursor.fetchall()
    if exact_95_docs:
        print(f"  Found {len(exact_95_docs)} documents with exactly 95.0% confidence:")
        for doc in exact_95_docs:
            print(f"    ID:{doc[0]} | {doc[2]} | Text: {doc[5]} (len: {doc[4] or 0})")
    else:
        print("  ✅ No documents with exactly 95.0% confidence")
    
    # Check overall OCR success rates
    print("\n3. Overall OCR Statistics:")
    cursor.execute("""
        SELECT 
            COUNT(*) as total_docs,
            COUNT(CASE WHEN ocr_text IS NOT NULL AND ocr_text != '' THEN 1 END) as with_text,
            COUNT(CASE WHEN ocr_text IS NULL OR ocr_text = '' THEN 1 END) as no_text,
            AVG(ocr_confidence_avg) as avg_confidence,
            MIN(ocr_confidence_avg) as min_confidence,
            MAX(ocr_confidence_avg) as max_confidence
        FROM single_documents 
        WHERE ocr_confidence_avg IS NOT NULL
    """)
    
    stats = cursor.fetchone()
    if stats:
        total, with_text, no_text, avg_conf, min_conf, max_conf = stats
        print(f"  Total documents: {total}")
        print(f"  With OCR text: {with_text} ({with_text/total*100:.1f}%)")
        print(f"  No OCR text: {no_text} ({no_text/total*100:.1f}%)")
        print(f"  Avg confidence: {avg_conf:.1f}%")
        print(f"  Confidence range: {min_conf:.1f}% - {max_conf:.1f}%")
    
    # Check for patterns in failed OCR
    print("\n4. OCR Failure Analysis:")
    cursor.execute("""
        SELECT id, batch_id, original_filename, file_size_bytes, page_count
        FROM single_documents 
        WHERE ocr_text IS NULL OR ocr_text = ''
        ORDER BY file_size_bytes DESC
        LIMIT 10
    """)
    
    failed_docs = cursor.fetchall()
    if failed_docs:
        print(f"  Top 10 largest files with OCR failures:")
        for doc in failed_docs:
            size_mb = doc[3] / (1024*1024) if doc[3] else 0
            print(f"    ID:{doc[0]} | {doc[2]} | {size_mb:.1f}MB | {doc[4]} pages")
    
    # Check for AI classifications without OCR text
    print("\n5. AI Classifications Without OCR Text:")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM single_documents 
        WHERE (ocr_text IS NULL OR ocr_text = '') 
          AND ai_suggested_category IS NOT NULL
    """)
    
    ai_without_ocr = cursor.fetchone()[0]
    if ai_without_ocr > 0:
        print(f"  ⚠️ {ai_without_ocr} documents have AI classifications but no OCR text!")
        print("  This suggests AI is 'hallucinating' classifications without content.")
    else:
        print("  ✅ All AI classifications are based on OCR text")
    
    conn.close()
    print("\n" + "=" * 50)
    print("Investigation complete. Check results above for anomalies.")

if __name__ == "__main__":
    investigate_ocr_anomalies()
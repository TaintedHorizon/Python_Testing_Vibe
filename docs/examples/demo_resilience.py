#!/usr/bin/env python3
"""
Batch Resilience Demo (archived example)

This file was moved from `doc_processor/dev_tools/demo_resilience.py` into
`docs/examples/` to keep developer tooling separate from core scripts. It
remains runnable as an example, but is not executed by tests.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from batch_resume import get_batch_completion_status, get_incomplete_documents, log_batch_resume_info
import sqlite3
from contextlib import contextmanager
import os


def _resolve_db_path():
    db_path = os.getenv('DATABASE_PATH')
    if not db_path:
        try:
            from config_manager import app_config
            db_path = getattr(app_config, 'DATABASE_PATH', None)
        except Exception:
            db_path = None
    if not db_path:
        db_path = os.path.join(os.path.dirname(__file__), 'documents.db')
    return db_path


@contextmanager
def database_connection():
    db_path = _resolve_db_path()
    try:
        try:
            from ..database import get_db_connection
            conn = get_db_connection()
        except Exception:
            try:
                from doc_processor.database import get_db_connection
                conn = get_db_connection()
            except Exception:
                try:
                    from doc_processor.dev_tools.db_connect import connect as db_connect
                    conn = db_connect(db_path)
                except Exception:
                    from sqlite3 import connect as sqlite_connect
                    conn = sqlite_connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def analyze_all_batches():
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, status FROM batches ORDER BY id DESC LIMIT 10")
            batches = cursor.fetchall()
            print("🔧 Batch Resilience Analysis")
            print("=" * 50)
            total_compute_saved = 0
            for batch_id, batch_status in batches:
                status = get_batch_completion_status(batch_id)
                if status.get('error'):
                    continue
                total_docs = status.get('total_documents', 0)
                analyzed_docs = status.get('analyzed_documents', 0)
                completed_docs = status.get('completed_documents', 0)
                if total_docs > 0:
                    cached_analyses = analyzed_docs
                    cached_ocr = status.get('ocr_completed_documents', 0)
                    llm_savings = cached_analyses * 15
                    ocr_savings = cached_ocr * 30
                    total_savings = llm_savings + ocr_savings
                    total_compute_saved += total_savings
                    print(f"\nBatch {batch_id}: {batch_status}")
                    print(f"  📄 Total Documents: {total_docs}")
                    print(f"  ✅ Completed: {completed_docs} ({completed_docs/total_docs*100:.1f}%)")
                    print(f"  🧠 AI Analysis Cached: {cached_analyses}")
                    print(f"  👁️ OCR Results Cached: {cached_ocr}")
                    print(f"  ⚡ LLM Compute Saved: {llm_savings}s ({llm_savings//60}m {llm_savings%60}s)")
                    print(f"  ⚡ OCR Compute Saved: {ocr_savings}s ({ocr_savings//60}m {ocr_savings%60}s)")
                    print(f"  🎯 TOTAL Saved: {total_savings}s ({total_savings//60}m {total_savings%60}s)")
                    if status.get('needs_resume'):
                        incomplete = get_incomplete_documents(batch_id)
                        print(f"  🔄 Can Resume: Yes ({len(incomplete)} docs remaining)")
                        print(f"  📍 Resume Point: {status.get('resume_point')}")
                    else:
                        print(f"  🔄 Can Resume: No (complete)")
            print(f"\n🎯 TOTAL COMPUTE SAVINGS AVAILABLE")
            print(f"⚡ {total_compute_saved}s saved ({total_compute_saved//60}m {total_compute_saved%60}s)")
    except Exception as e:
        print(f"Error analyzing batches: {e}")


def demo_cache_hit_simulation():
    print(f"\n📚 Cache Hit Simulation")
    print("=" * 30)
    print("Scenario: Batch interrupted at 60% completion")
    print("Before Resilience: 100% compute waste (restart from 0%)")
    print("After Resilience:  40% compute needed (resume from 60%)")
    print("Compute Saved:     60% (cached analysis + resumability)")


if __name__ == "__main__":
    analyze_all_batches()
    demo_cache_hit_simulation()

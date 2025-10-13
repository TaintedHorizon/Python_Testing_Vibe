#!/usr/bin/env python3
"""
Batch Resilience Demo

Demonstrates the new caching and resumability features.
Run this to see current batch states and potential compute savings.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from batch_resume import get_batch_completion_status, get_incomplete_documents, log_batch_resume_info
import sqlite3
from contextlib import contextmanager
import os


def _resolve_db_path():
    # Prefer explicit env override (used by tests), then app_config, then repo-local fallback
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
    """Simple database connection for demo that respects configured DATABASE_PATH."""
    db_path = _resolve_db_path()
    # Prefer app's DB helper when available
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
                conn = db_connect(db_path, timeout=30.0)
            except Exception:
                from .db_connect import connect as db_connect
                conn = db_connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def analyze_all_batches():
    """Analyze all batches to show resilience improvements."""
    try:
        with database_connection() as conn:
            cursor = conn.cursor()

            # Get all batches
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
                    # Calculate potential compute savings
                    cached_analyses = analyzed_docs
                    cached_ocr = status.get('ocr_completed_documents', 0)

                    # Estimate compute time saved
                    llm_savings = cached_analyses * 15  # ~15 seconds per LLM call
                    ocr_savings = cached_ocr * 30       # ~30 seconds per OCR processing
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
                        print("  🔄 Can Resume: No (complete)")

            print("\n🎯 TOTAL COMPUTE SAVINGS AVAILABLE")
            print(f"⚡ {total_compute_saved}s saved ({total_compute_saved//60}m {total_compute_saved%60}s)")
            print(f"💰 LLM calls avoided: ~{total_compute_saved//45} (15s each + 30s OCR)")
            print("🔥 This represents MASSIVE compute waste elimination!")

            # Show current batch 4 status if it exists
            if any(bid == 4 for bid, _ in batches):
                print("\n🔍 Current Batch 4 Detailed Status:")
                log_batch_resume_info(4)

    except Exception as e:
        print(f"Error analyzing batches: {e}")


def demo_cache_hit_simulation():
    """Simulate what happens when a batch is interrupted and resumed."""
    print("\n📚 Cache Hit Simulation")
    print("=" * 30)
    print("Scenario: Batch interrupted at 60% completion")
    print("Before Resilience: 100% compute waste (restart from 0%)")
    print("After Resilience:  40% compute needed (resume from 60%)")
    print("Compute Saved:     60% (cached analysis + resumability)")
    print("")
    print("For 30 documents:")
    print("  OCR Processing:")
    print("    Without caching: 30 × 30s = 900s (15 minutes)")
    print("    With caching:    12 × 30s = 360s (6 minutes)")
    print("    OCR time saved:  540s (9 minutes) = 60% reduction")
    print("")
    print("  LLM Analysis:")
    print("    Without caching: 30 × 15s = 450s (7.5 minutes)")
    print("    With caching:    12 × 15s = 180s (3 minutes)")
    print("    LLM time saved:  270s (4.5 minutes) = 60% reduction")
    print("")
    print("  TOTAL TIME SAVED: 810s (13.5 minutes) = 60% reduction")
    print("  User Experience: No more sitting through 30 re-analyses!")


if __name__ == "__main__":
    analyze_all_batches()
    demo_cache_hit_simulation()
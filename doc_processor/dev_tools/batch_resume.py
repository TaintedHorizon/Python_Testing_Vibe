"""
Batch Resumability Functions

Provides functions to check batch completion status and resume interrupted processing.
"""

import logging
from typing import List, Dict, Any
import sys
import os

# Add the parent directory to the path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from processing import database_connection
except ImportError:
    # Fallback for standalone execution
    import sqlite3
    from contextlib import contextmanager

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
        """Fallback database connection that respects configured DATABASE_PATH."""
        db_path = _resolve_db_path()
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
                        conn = db_connect(db_path, timeout=30.0)
        assert conn is not None
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


def get_batch_completion_status(batch_id: int) -> Dict[str, Any]:
    """
    Check the completion status of a batch.

    Args:
        batch_id: ID of the batch to check

    Returns:
        dict: Completion status with detailed breakdown
    """
    try:
        with database_connection() as conn:
            cursor = conn.cursor()

            # Get batch info
            cursor.execute("SELECT status FROM batches WHERE id = ?", (batch_id,))
            batch_row = cursor.fetchone()
            if not batch_row:
                return {"error": f"Batch {batch_id} not found"}

            batch_status = batch_row[0]

            # Get document completion stats
            cursor.execute("""
                SELECT
                    COUNT(*) as total_docs,
                    COUNT(CASE WHEN status = 'ready_for_manipulation' THEN 1 END) as completed_docs,
                    COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing_docs,
                    COUNT(CASE WHEN ai_suggested_category IS NOT NULL THEN 1 END) as analyzed_docs,
                    COUNT(CASE WHEN ocr_text IS NOT NULL THEN 1 END) as ocr_completed_docs,
                    COUNT(CASE WHEN searchable_pdf_path IS NOT NULL THEN 1 END) as searchable_pdfs
                FROM single_documents
                WHERE batch_id = ?
            """, (batch_id,))

            stats = cursor.fetchone()
            if not stats:
                return {
                    "batch_id": batch_id,
                    "batch_status": batch_status,
                    "total_documents": 0,
                    "completion_percentage": 100.0,
                    "needs_resume": False,
                    "resume_point": "completed"
                }

            total, completed, processing, analyzed, ocr_completed, searchable_pdfs = stats

            # Determine resume point
            needs_resume = batch_status == "processing" and completed < total
            completion_percentage = (completed / total * 100) if total > 0 else 100.0

            resume_point = "completed"
            if needs_resume:
                if ocr_completed < total:
                    resume_point = "ocr_processing"
                elif analyzed < total:
                    resume_point = "ai_analysis"
                else:
                    resume_point = "finalization"

            return {
                "batch_id": batch_id,
                "batch_status": batch_status,
                "total_documents": total,
                "completed_documents": completed,
                "processing_documents": processing,
                "analyzed_documents": analyzed,
                "ocr_completed_documents": ocr_completed,
                "completion_percentage": completion_percentage,
                "needs_resume": needs_resume,
                "resume_point": resume_point
            }
    except Exception as e:
        logging.error(f"Error checking batch {batch_id} completion status: {e}")
        return {"error": str(e)}


def get_incomplete_documents(batch_id: int) -> List[Dict[str, Any]]:
    """
    Get list of documents in a batch that still need processing.

    Args:
        batch_id: ID of the batch to check

    Returns:
        list: Documents that need processing
    """
    try:
        with database_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    id, original_filename, status,
                    (ocr_text IS NOT NULL) as has_ocr,
                    (ai_suggested_category IS NOT NULL) as has_ai_analysis
                FROM single_documents
                WHERE batch_id = ? AND status != 'ready_for_manipulation'
                ORDER BY id
            """, (batch_id,))

            incomplete = []
            for row in cursor.fetchall():
                doc_id, filename, status, has_ocr, has_ai_analysis = row

                next_step = "unknown"
                if not has_ocr:
                    next_step = "ocr_processing"
                elif not has_ai_analysis:
                    next_step = "ai_analysis"
                else:
                    next_step = "finalization"

                incomplete.append({
                    "document_id": doc_id,
                    "filename": filename,
                    "status": status,
                    "has_ocr": bool(has_ocr),
                    "has_ai_analysis": bool(has_ai_analysis),
                    "next_step": next_step
                })

            return incomplete

    except Exception as e:
        logging.error(f"Error getting incomplete documents for batch {batch_id}: {e}")
        return []


def can_resume_batch(batch_id: int) -> bool:
    """
    Check if a batch can be safely resumed.

    Args:
        batch_id: ID of the batch to check

    Returns:
        bool: True if batch can be resumed
    """
    status = get_batch_completion_status(batch_id)
    return status.get("needs_resume", False) and status.get("total_documents", 0) > 0


def log_batch_resume_info(batch_id: int) -> None:
    """
    Log detailed information about batch resume status.

    Args:
        batch_id: ID of the batch to log info for
    """
    status = get_batch_completion_status(batch_id)
    incomplete = get_incomplete_documents(batch_id)

    logging.info(f"📊 Batch {batch_id} Resume Status:")
    logging.info(f"   Total Documents: {status.get('total_documents', 0)}")
    logging.info(f"   Completed: {status.get('completed_documents', 0)}")
    logging.info(f"   Completion: {status.get('completion_percentage', 0):.1f}%")
    logging.info(f"   Resume Point: {status.get('resume_point', 'unknown')}")
    logging.info(f"   Needs Resume: {status.get('needs_resume', False)}")

    if incomplete:
        logging.info(f"   Incomplete Documents: {len(incomplete)}")
        for doc in incomplete[:5]:  # Show first 5
            logging.info(f"     - {doc['filename']}: {doc['next_step']}")
        if len(incomplete) > 5:
            logging.info(f"     ... and {len(incomplete) - 5} more")
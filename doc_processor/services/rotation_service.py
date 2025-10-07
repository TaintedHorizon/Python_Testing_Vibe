"""Rotation service encapsulating physical PDF rotation and rotation state persistence.

Responsibilities:
- Validate rotation angles
- Physically rotate PDF pages using PyMuPDF
- Reset (or set) rotation value in intake_rotations table
- Provide structured result for API layer

This isolates rotation logic away from route handlers so both API and future
background tasks can reuse it.
"""
from __future__ import annotations
import os
import logging
from typing import Dict, Any, List

from ..database import get_db_connection

logger = logging.getLogger(__name__)

VALID_ROTATIONS = {0, 90, 180, 270}

# New logical rotation table (document_id keyed) replacing filename-based intake_rotations for UI consistency.
LOGICAL_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS document_rotations (
  document_id INTEGER PRIMARY KEY,
  rotation INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

def _ensure_logical_table(cur):
    cur.execute(LOGICAL_TABLE_SQL)

def get_logical_rotation(document_id: int) -> int:
    """Return stored logical rotation (0 if none)."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        _ensure_logical_table(cur)
        row = cur.execute("SELECT rotation FROM document_rotations WHERE document_id=?", (document_id,)).fetchone()
        return int(row[0]) % 360 if row else 0
    finally:
        conn.close()

def set_logical_rotation(document_id: int, rotation: int) -> Dict[str, any]:
    """Persist logical rotation for a document (no physical file change)."""
    if rotation not in VALID_ROTATIONS:
        return {"success": False, "error": "Invalid rotation angle", "status_code": 400}
    conn = get_db_connection()
    try:
        cur = conn.cursor(); _ensure_logical_table(cur)
        cur.execute("SELECT 1 FROM document_rotations WHERE document_id=?", (document_id,))
        if cur.fetchone():
            cur.execute("UPDATE document_rotations SET rotation=?, updated_at=CURRENT_TIMESTAMP WHERE document_id=?", (rotation, document_id))
        else:
            cur.execute("INSERT INTO document_rotations (document_id, rotation) VALUES (?, ?)", (document_id, rotation))
        conn.commit()
        return {"success": True, "rotation": rotation}
    except Exception as e:  # pragma: no cover
        logger.error(f"set_logical_rotation failed doc {document_id}: {e}")
        return {"success": False, "error": str(e), "status_code": 500}
    finally:
        conn.close()


def apply_physical_rotation(doc_id: int, rotation: int) -> Dict[str, Any]:
    """Physically rotate a single-document PDF and clear logical rotation.

    Args:
        doc_id: ID in single_documents table
        rotation: Desired clockwise rotation (0,90,180,270)

    Returns:
        dict with keys:
          success (bool)
          message (str)
          rotation (int) resulting logical rotation (always 0 after physical)
          physical (bool) whether a physical change was performed
          prev_page_rotations (List[int]) previous per-page rotations (if physical)
    """
    if rotation not in VALID_ROTATIONS:
        return {"success": False, "error": "Invalid rotation angle", "status_code": 400}

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        row = cur.execute("SELECT original_filename, original_pdf_path FROM single_documents WHERE id=?", (doc_id,)).fetchone()
        if not row:
            return {"success": False, "error": "Document not found", "status_code": 404}
        filename, pdf_path = row[0], row[1]
        if not pdf_path or not os.path.exists(pdf_path):
            return {"success": False, "error": "Stored PDF path missing", "status_code": 404}

        # Ensure rotations table exists
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS intake_rotations (
              filename TEXT PRIMARY KEY,
              rotation INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if rotation == 0:
            # Clear rotation entry only
            cur.execute("SELECT 1 FROM intake_rotations WHERE filename=?", (filename,))
            if cur.fetchone():
                cur.execute("UPDATE intake_rotations SET rotation=0, updated_at=CURRENT_TIMESTAMP WHERE filename=?", (filename,))
            else:
                cur.execute("INSERT INTO intake_rotations (filename, rotation) VALUES (?, 0)", (filename,))
            conn.commit()
            return {"success": True, "message": "Rotation cleared", "rotation": 0, "physical": False}

        # Perform physical rotation
        prev_page_rotations: List[int] = []
        try:
            import fitz  # type: ignore
            doc = fitz.open(pdf_path)
            for page in doc:
                prev_page_rotations.append(page.rotation)
                page.set_rotation((page.rotation + rotation) % 360)
            tmp_path = pdf_path + '.rotating_tmp'
            doc.save(tmp_path, incremental=False, deflate=True)
            doc.close()
            os.replace(tmp_path, pdf_path)
        except Exception as phys_err:  # pragma: no cover - environment specific
            logger.error(f"Physical rotation failed for doc {doc_id}: {phys_err}")
            return {"success": False, "error": f"Physical rotation failed: {phys_err}", "status_code": 500}

        # Reset logical rotation to 0 (baked into file now)
        cur.execute("SELECT 1 FROM intake_rotations WHERE filename=?", (filename,))
        if cur.fetchone():
            cur.execute("UPDATE intake_rotations SET rotation=0, updated_at=CURRENT_TIMESTAMP WHERE filename=?", (filename,))
        else:
            cur.execute("INSERT INTO intake_rotations (filename, rotation) VALUES (?, 0)", (filename,))
        conn.commit()
        return {
            "success": True,
            "message": f"Applied {rotation}° rotation",
            "rotation": 0,
            "physical": True,
            "prev_page_rotations": prev_page_rotations,
            "applied_delta": rotation,
        }
    except Exception as e:  # pragma: no cover
        logger.error(f"apply_physical_rotation unexpected error doc {doc_id}: {e}")
        return {"success": False, "error": str(e), "status_code": 500}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

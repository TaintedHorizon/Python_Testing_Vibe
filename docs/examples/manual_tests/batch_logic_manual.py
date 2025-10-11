#!/usr/bin/env python3
"""
Manual batch logic diagnostic (archived from dev_tools/test_batch_logic.py).

Run manually with the project venv activated. Not intended for CI.
"""
from doc_processor.app import get_db_connection


def run():
    conn = get_db_connection()
    try:
        batch_raw = conn.execute("SELECT * FROM batches WHERE id = 4").fetchone()
        if not batch_raw:
            print("Batch 4 not found - manual diagnostic")
            return
        print(dict(batch_raw))
    finally:
        conn.close()


if __name__ == '__main__':
    run()

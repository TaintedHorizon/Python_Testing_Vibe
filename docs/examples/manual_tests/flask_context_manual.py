#!/usr/bin/env python3
"""
Manual Flask context diagnostic script (archived).

Moved from `doc_processor/dev_tools/test_flask_context_fix.py` and renamed to
avoid pytest collection. Intended for manual verification only.
"""
from doc_processor.app import create_app


def run_check():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        resp = client.get('/api/smart_processing_progress')
        print('Status:', resp.status_code, 'Mimetype:', resp.mimetype)


if __name__ == '__main__':
    run_check()

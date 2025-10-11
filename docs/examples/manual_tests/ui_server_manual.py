#!/usr/bin/env python3
"""
Manual UI server diagnostic (archived from dev_tools/test_ui_server.py).

Run manually; not collected by pytest.
"""
from doc_processor.app import create_app


def run_check():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        r = client.get('/')
        print('Index status:', r.status_code)


if __name__ == '__main__':
    run_check()

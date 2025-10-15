from doc_processor.app import create_app


def test_smart_processing_progress_route_no_500():
    """Ensure the smart processing SSE route does not raise a 500 on GET."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        resp = client.get('/api/smart_processing_progress')
        # Route should be accessible and not return 5xx
        assert resp.status_code < 500
        # If route exists (200), check SSE mimetype; otherwise accept 404/302 as long as it's not 5xx
        if resp.status_code == 200:
            assert resp.mimetype in ('text/event-stream', 'text/plain', 'application/octet-stream')

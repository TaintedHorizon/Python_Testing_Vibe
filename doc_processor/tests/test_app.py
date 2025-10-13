from doc_processor import app

def test_home_route():
    test_client = app.app.test_client()
    response = test_client.get('/')
    assert response.status_code == 200
    assert b"Batch Control" in response.data

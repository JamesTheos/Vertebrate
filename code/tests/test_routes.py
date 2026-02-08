def test_index_route(client):
    # The app defines both '/' mapped to either initial-index or index depending on DB state,
    # but '/index' is always available.
    resp = client.get('/index')
    assert resp.status_code == 200
    assert b'<html' in resp.data.lower()  # crude check that we rendered a template


def test_health_of_some_pages(client):
    # Pages that don’t require Kafka or auth middlewares
    for path in ['/login-error', '/logout-message', '/updated-user']:
        r = client.get(path)
        assert r.status_code == 200

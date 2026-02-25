def test_index_route(client):
    resp = client.get('/index')
    assert resp.status_code == 200
    assert b'<html' in resp.data.lower()


def test_health_of_some_pages(client):
    # Only test routes that return redirects or simple responses
    # (templates not guaranteed in test env)
    for path in ['/login-error', '/logout-message']:
        r = client.get(path)
        assert r.status_code in (200, 302), f"{path} returned {r.status_code}"

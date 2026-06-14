"""
test_app_security.py

The Flask secret_key signs the session cookie.  It used to be hardcoded
(`app.secret_key = 'your_secret_key'`) — a predictable key lets anyone forge
session cookies.  These tests pin the hardened behaviour: the key comes from the
SECRET_KEY environment variable, and the old placeholder is never used.
"""


def test_secret_key_from_env(monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'env-provided-key-abc123')
    from app import create_app
    app = create_app()
    assert app.secret_key == 'env-provided-key-abc123'


def test_secret_key_not_hardcoded_placeholder(monkeypatch):
    monkeypatch.delenv('SECRET_KEY', raising=False)
    from app import create_app
    app = create_app()
    assert app.secret_key, 'secret_key must not be empty'
    assert app.secret_key != 'your_secret_key', \
        'secret_key must not fall back to the hardcoded placeholder'

"""
test_merge_aas.py

Merge step 4 (feature/aas-integration): main and the aas branch both changed the
login handling, the idle logout and the blueprint registration in app.py /
timeout.py.  These tests pin what the merged app must do:

- both blueprints (audit_bp, aas_bp) are registered
- unauthenticated /api/... and /audit/api/... calls get a JSON 401; browser
  pages keep main's redirect (the demo shows Home with "Please log in")
- SESSION_IDLE_MINUTES still sets the idle logout (the demo uses 60 min; the aas
  branch hard-coded 5 min), and an idle API call gets a JSON 401
- /login answers 200 for guests (Docker HEALTHCHECK of the aas Dockerfile)
"""

import importlib
from datetime import datetime, timedelta, UTC

import pytest
from werkzeug.security import generate_password_hash

import timeout

USERNAME = 'merge.aas'
AAS_URL = '/api/aas/equipment/filling-machine-1'


@pytest.fixture(scope='module')
def user_id(app):
    from models import db, User
    with app.app_context():
        user = User.query.filter_by(username=USERNAME).first()
        if not user:
            user = User(username=USERNAME, password=generate_password_hash('merge-pw'))
            db.session.add(user)
            db.session.commit()
        return user.id


def client_idle_for(app, user_id, minutes):
    """A logged-in client whose last request was `minutes` ago."""
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True
        session['last_activity'] = (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()
    return client


def test_audit_and_aas_blueprints_registered(app):
    assert 'audit' in app.blueprints
    assert 'aas' in app.blueprints


@pytest.mark.parametrize('path', [AAS_URL, '/audit/api/stats'])
def test_unauthenticated_api_call_gets_json_401(client, path):
    resp = client.get(path)
    assert resp.status_code == 401
    assert resp.is_json and 'error' in resp.get_json()


def test_unauthenticated_page_keeps_mains_redirect(client):
    resp = client.get('/audit/')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/index')


def test_login_page_answers_200_for_guests(client):
    assert client.get('/login').status_code == 200


def test_session_idle_minutes_sets_the_idle_logout(monkeypatch):
    monkeypatch.setenv('SESSION_IDLE_MINUTES', '60')
    try:
        assert importlib.reload(timeout).INACTIVITY_TIMEOUT == 3600
    finally:
        monkeypatch.delenv('SESSION_IDLE_MINUTES')
        importlib.reload(timeout)


@pytest.mark.parametrize('minutes, logged_in', [(30, True), (61, False)])
def test_idle_logout_follows_the_configured_minutes(app, user_id, monkeypatch, minutes, logged_in):
    monkeypatch.setattr(timeout, 'INACTIVITY_TIMEOUT', 3600)
    resp = client_idle_for(app, user_id, minutes).get('/user-profile')
    assert (resp.status_code == 200) == logged_in
    if not logged_in:
        assert resp.headers['Location'].endswith('/logout-message')


@pytest.mark.parametrize('path', [AAS_URL, '/audit/api/stats'])
def test_idle_api_call_gets_json_401(app, user_id, monkeypatch, path):
    monkeypatch.setattr(timeout, 'INACTIVITY_TIMEOUT', 300)
    resp = client_idle_for(app, user_id, 10).get(path)
    assert resp.status_code == 401
    assert resp.is_json and 'error' in resp.get_json()

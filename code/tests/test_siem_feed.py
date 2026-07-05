"""
test_siem_feed.py
TDD tests for the SIEM audit-feed endpoint — GET /audit/api/siem.
Token-authenticated (API key, not session), cursor-paginated NDJSON feed
so a SIEM (Splunk / Sentinel / QRadar / Elastic) can tail the audit trail.

Run: docker cp code/tests/test_siem_feed.py <app-container>:/app/code/tests/ &&
     docker exec <app-container> python -m pytest /app/code/tests/test_siem_feed.py -v
"""
import os
import hashlib
import pytest

os.environ.setdefault('DISABLE_KAFKA', '1')

RAW_KEY = 'test-siem-raw-key-for-pytest-only'
INACTIVE_RAW_KEY = 'test-siem-inactive-key-for-pytest'


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def app():
    from app import create_app
    flask_app = create_app()
    flask_app.config['TESTING'] = True
    with flask_app.app_context():
        yield flask_app


@pytest.fixture(scope='module')
def client(app):
    return app.test_client()


@pytest.fixture(scope='module')
def siem_key(app):
    """Provision one active and one inactive API key directly in the DB."""
    from models import db, SiemApiKey
    with app.app_context():
        for name, raw, active in [
            ('pytest-active', RAW_KEY, True),
            ('pytest-inactive', INACTIVE_RAW_KEY, False),
        ]:
            if not SiemApiKey.query.filter_by(name=name).first():
                db.session.add(SiemApiKey(
                    name=name,
                    key_hash=hashlib.sha256(raw.encode()).hexdigest(),
                    active=active,
                ))
        db.session.commit()
    return RAW_KEY


def _bearer(key):
    return {'Authorization': f'Bearer {key}'}


# ── Step 1: Auth gate ─────────────────────────────────────────────────────────

def test_siem_requires_key(client, siem_key):
    resp = client.get('/audit/api/siem')
    assert resp.status_code == 401
    assert resp.is_json
    assert 'error' in resp.get_json()


def test_siem_rejects_bad_key(client, siem_key):
    resp = client.get('/audit/api/siem', headers=_bearer('wrong-key'))
    assert resp.status_code == 401
    assert resp.is_json


def test_siem_rejects_inactive_key(client, siem_key):
    resp = client.get('/audit/api/siem', headers=_bearer(INACTIVE_RAW_KEY))
    assert resp.status_code == 401
    assert resp.is_json


def test_siem_accepts_valid_key_bearer(client, siem_key):
    resp = client.get('/audit/api/siem', headers=_bearer(siem_key))
    assert resp.status_code == 200


def test_siem_accepts_valid_key_x_api_key(client, siem_key):
    resp = client.get('/audit/api/siem', headers={'X-API-Key': siem_key})
    assert resp.status_code == 200

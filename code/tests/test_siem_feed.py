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
from datetime import datetime, timezone

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


@pytest.fixture(scope='module')
def seeded_logs(app):
    """Insert 6 audit entries with valid checksums; returns their ids ascending."""
    from models import db, AuditLog
    from audit_trail import _generate_checksum

    specs = [
        dict(action_type='LOGIN', record_type='USER'),
        dict(action_type='CREATE', record_type='ORDER', record_id='SIEM-001'),
        dict(action_type='UPDATE', record_type='ORDER', record_id='SIEM-001',
             field_name='status', old_value='Created', new_value='Released'),
        dict(action_type='LOGIN_FAILED', record_type='USER'),
        dict(action_type='DELETE', record_type='ORDER', record_id='SIEM-002',
             change_reason='pytest cleanup'),
        dict(action_type='LOGOUT', record_type='USER'),
    ]
    with app.app_context():
        entries = []
        for i, spec in enumerate(specs):
            e = AuditLog(
                timestamp=datetime(2026, 4, 1, 10, i, 0, tzinfo=timezone.utc),
                username='User_Admin', ip_address='10.0.0.9',
                endpoint='pytest', **spec
            )
            e.checksum = _generate_checksum(e)
            db.session.add(e)
            entries.append(e)
        db.session.commit()
        return [e.id for e in entries]


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


# ── Step 2: Cursor pagination (?since_id / ?limit) ────────────────────────────

def _get_json(client, key, **params):
    params['format'] = 'json'
    qs = '&'.join(f'{k}={v}' for k, v in params.items())
    resp = client.get(f'/audit/api/siem?{qs}', headers=_bearer(key))
    assert resp.status_code == 200
    return resp.get_json()


def test_siem_returns_events_after_since_id(client, siem_key, seeded_logs):
    data = _get_json(client, siem_key, since_id=seeded_logs[2])
    ids = [e['id'] for e in data['events']]
    assert ids == seeded_logs[3:]            # strictly id > since_id
    assert ids == sorted(ids)                # ascending — tail-safe
    assert data['has_more'] is False


def test_siem_respects_limit_and_reports_next_cursor(client, siem_key, seeded_logs):
    data = _get_json(client, siem_key, since_id=seeded_logs[0], limit=2)
    ids = [e['id'] for e in data['events']]
    assert ids == seeded_logs[1:3]
    assert data['has_more'] is True
    assert data['next_since_id'] == seeded_logs[2]

    # Following the cursor yields the remainder with no skips or repeats
    data2 = _get_json(client, siem_key, since_id=data['next_since_id'])
    assert [e['id'] for e in data2['events']] == seeded_logs[3:]


def test_siem_empty_when_caught_up(client, siem_key, seeded_logs):
    data = _get_json(client, siem_key, since_id=seeded_logs[-1])
    assert data['events'] == []
    assert data['has_more'] is False

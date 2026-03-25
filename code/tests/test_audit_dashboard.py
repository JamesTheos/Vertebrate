"""
test_audit_dashboard.py
TDD tests for the Audit Dashboard Blueprint — 21 CFR Part 11
Run: docker compose exec vertebrate-app sh -c \
     "cd /app/code && python -m pytest tests/test_audit_dashboard.py -v"
"""
import os
import json
import pytest
from datetime import datetime, timezone

os.environ.setdefault('DISABLE_KAFKA', '1')


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def app():
    from app import create_app
    flask_app = create_app()
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    with flask_app.app_context():
        yield flask_app


@pytest.fixture(scope='module')
def client(app):
    return app.test_client()


@pytest.fixture(scope='module')
def logged_in_client(app, client):
    """Authenticated client (User_Admin)."""
    client.post(
        '/loginUser',
        data=json.dumps({'username': 'User_Admin', 'password': '12345'}),
        content_type='application/json'
    )
    return client


@pytest.fixture(scope='module')
def seeded_logs(app):
    """Seed a known set of AuditLog rows for dashboard queries.
    Note: no teardown — audit_trail.audit_logs is immutable per 21 CFR Part 11.
    Rows seeded here persist in the DB, which is correct compliance behaviour.
    """
    from models import db, AuditLog
    entries = [
        AuditLog(
            timestamp=datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
            username='User_Admin', action_type='LOGIN',
            record_type='USER', checksum='abc'
        ),
        AuditLog(
            timestamp=datetime(2026, 3, 1, 11, 0, 0, tzinfo=timezone.utc),
            username='User_Admin', action_type='CREATE',
            record_type='ORDER', record_id='ORD-001', checksum='def'
        ),
        AuditLog(
            timestamp=datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc),
            username='User_Admin', action_type='UPDATE',
            record_type='ORDER', record_id='ORD-001',
            field_name='status', old_value='Created', new_value='Released',
            checksum='ghi'
        ),
        AuditLog(
            timestamp=datetime(2026, 3, 2, 9, 30, 0, tzinfo=timezone.utc),
            username='User_Admin', action_type='LOGIN_FAILED',
            record_type='USER', checksum='jkl'
        ),
        AuditLog(
            timestamp=datetime(2026, 3, 3, 8, 0, 0, tzinfo=timezone.utc),
            username='User_Admin', action_type='DELETE',
            record_type='ROLE', record_id='5',
            change_reason='Role decommissioned', checksum='mno'
        ),
    ]
    with app.app_context():
        for e in entries:
            db.session.add(e)
        db.session.commit()
    yield



# ── Route: GET /audit/ ────────────────────────────────────────────────────────

class TestDashboardIndexRoute:

    def test_unauthenticated_redirects_to_login(self, client):
        resp = client.get('/audit/')
        assert resp.status_code in (302, 401), \
            "Unauthenticated request must be redirected or rejected"

    def test_authenticated_returns_200(self, logged_in_client):
        resp = logged_in_client.get('/audit/')
        assert resp.status_code == 200

    def test_response_is_html(self, logged_in_client):
        resp = logged_in_client.get('/audit/')
        assert b'<html' in resp.data or b'<!DOCTYPE html>' in resp.data

    def test_response_contains_audit_heading(self, logged_in_client):
        resp = logged_in_client.get('/audit/')
        assert b'Audit' in resp.data


# ── Route: GET /audit/api/stats ───────────────────────────────────────────────

class TestStatsAPI:

    def test_unauthenticated_returns_401_or_redirect(self, client):
        resp = client.get('/audit/api/stats')
        assert resp.status_code in (302, 401)

    def test_returns_200_and_json(self, logged_in_client, seeded_logs):
        resp = logged_in_client.get('/audit/api/stats')
        assert resp.status_code == 200
        assert resp.content_type.startswith('application/json')

    def test_has_required_keys(self, logged_in_client, seeded_logs):
        data = json.loads(logged_in_client.get('/audit/api/stats').data)
        for key in ('total_logs', 'by_action', 'by_record_type',
                    'failed_logins', 'logs_by_day'):
            assert key in data, f"Missing key: '{key}'"

    def test_total_logs_is_integer(self, logged_in_client, seeded_logs):
        data = json.loads(logged_in_client.get('/audit/api/stats').data)
        assert isinstance(data['total_logs'], int)

    def test_failed_logins_gte_one(self, logged_in_client, seeded_logs):
        data = json.loads(logged_in_client.get('/audit/api/stats').data)
        assert data['failed_logins'] >= 1

    def test_by_action_contains_seeded_types(self, logged_in_client, seeded_logs):
        data = json.loads(logged_in_client.get('/audit/api/stats').data)
        assert isinstance(data['by_action'], dict)
        for action in ('LOGIN', 'CREATE', 'UPDATE'):
            assert action in data['by_action']

    def test_logs_by_day_is_list_with_date_and_count(self, logged_in_client, seeded_logs):
        data = json.loads(logged_in_client.get('/audit/api/stats').data)
        assert isinstance(data['logs_by_day'], list)
        if data['logs_by_day']:
            entry = data['logs_by_day'][0]
            assert 'date' in entry and 'count' in entry


# ── Route: GET /audit/api/logs ────────────────────────────────────────────────

class TestLogsAPI:

    def test_unauthenticated_returns_401_or_redirect(self, client):
        resp = client.get('/audit/api/logs')
        assert resp.status_code in (302, 401)

    def test_returns_200_and_json(self, logged_in_client, seeded_logs):
        resp = logged_in_client.get('/audit/api/logs')
        assert resp.status_code == 200
        assert resp.content_type.startswith('application/json')

    def test_response_has_pagination_envelope(self, logged_in_client, seeded_logs):
        data = json.loads(logged_in_client.get('/audit/api/logs').data)
        for key in ('logs', 'total', 'page', 'pages', 'per_page'):
            assert key in data, f"Missing pagination key: '{key}'"

    def test_log_entry_has_all_fields(self, logged_in_client, seeded_logs):
        data = json.loads(logged_in_client.get('/audit/api/logs').data)
        assert data['logs'], "Expected at least one log entry"
        entry = data['logs'][0]
        for field in ('id', 'timestamp', 'username', 'action_type',
                      'record_type', 'record_id', 'field_name',
                      'old_value', 'new_value', 'change_reason',
                      'ip_address', 'endpoint', 'checksum'):
            assert field in entry, f"Log entry missing field: '{field}'"

    def test_filter_by_action_type(self, logged_in_client, seeded_logs):
        data = json.loads(
            logged_in_client.get('/audit/api/logs?action_type=LOGIN').data)
        for e in data['logs']:
            assert e['action_type'] == 'LOGIN'

    def test_filter_by_username(self, logged_in_client, seeded_logs):
        data = json.loads(
            logged_in_client.get('/audit/api/logs?username=User_Admin').data)
        for e in data['logs']:
            assert e['username'] == 'User_Admin'

    def test_filter_by_record_type(self, logged_in_client, seeded_logs):
        data = json.loads(
            logged_in_client.get('/audit/api/logs?record_type=ORDER').data)
        for e in data['logs']:
            assert e['record_type'] == 'ORDER'

    def test_per_page_limits_results(self, logged_in_client, seeded_logs):
        data = json.loads(
            logged_in_client.get('/audit/api/logs?per_page=2&page=1').data)
        assert len(data['logs']) <= 2

    def test_default_sort_newest_first(self, logged_in_client, seeded_logs):
        data = json.loads(
            logged_in_client.get('/audit/api/logs?per_page=50').data)
        timestamps = [e['timestamp'] for e in data['logs']]
        assert timestamps == sorted(timestamps, reverse=True), \
            "Default sort must be newest-first"


# ── Route: GET /audit/api/integrity ──────────────────────────────────────────

class TestIntegrityAPI:

    def test_unauthenticated_returns_401_or_redirect(self, client):
        resp = client.get('/audit/api/integrity')
        assert resp.status_code in (302, 401)

    def test_returns_200_and_json(self, logged_in_client):
        resp = logged_in_client.get('/audit/api/integrity')
        assert resp.status_code == 200
        assert resp.content_type.startswith('application/json')

    def test_response_has_required_keys(self, logged_in_client):
        data = json.loads(logged_in_client.get('/audit/api/integrity').data)
        for key in ('total_checked', 'tampered', 'tampered_ids'):
            assert key in data, f"Missing key: '{key}'"

    def test_tampered_is_int_and_ids_is_list(self, logged_in_client):
        data = json.loads(logged_in_client.get('/audit/api/integrity').data)
        assert isinstance(data['tampered'], int)
        assert isinstance(data['tampered_ids'], list)
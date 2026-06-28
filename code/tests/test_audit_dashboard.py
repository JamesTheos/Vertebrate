"""
test_audit_dashboard.py
TDD tests for the Audit Dashboard Blueprint — 21 CFR Part 11
Run: docker compose exec vertebrate-app sh -c \
     "cd /app && python -m pytest code/tests/test_audit_dashboard.py -v --tb=short"
"""
import os
import json
import pytest
from datetime import datetime, timezone

os.environ.setdefault('DISABLE_KAFKA', '1')


# ── Fixtures ──────────────────────────────────────────────────────────────────

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


@pytest.fixture()
def anon_client():
    """Completely isolated app instance — guaranteed unauthenticated."""
    import os
    os.environ.setdefault('DISABLE_KAFKA', '1')
    from app import create_app
    fresh_app = create_app()
    fresh_app.config['TESTING'] = True
    with fresh_app.app_context():
        yield fresh_app.test_client()


def _grant_audit_view(app):
    """Grant the seeded User_Admin the 'audit-view' permission via its role."""
    from models import db, User, Permission, RolePermission
    with app.app_context():
        perm = Permission.query.filter_by(key='audit-view').first()
        if not perm:
            perm = Permission(key='audit-view')
            db.session.add(perm)
            db.session.flush()
        user = User.query.filter_by(username='User_Admin').first()
        role = user.roles[0]
        if not RolePermission.query.filter_by(
                role_id=role.id, permission_id=perm.id).first():
            db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        db.session.commit()


@pytest.fixture(scope='module')
def logged_in_client(app, client):
    client.post(
        '/loginUser',                          # ← matches auth.loginUser route
        data=json.dumps({'username': 'User_Admin', 'password': '12345'}),
        content_type='application/json'
    )
    _grant_audit_view(app)                      # audit routes require 'audit-view'
    return client


@pytest.fixture()
def noperm_client():
    """Authenticated as the seeded admin but WITHOUT 'audit-view' — isolated app
    so no other test's grant leaks in.  Used to assert the permission gate."""
    import os
    os.environ.setdefault('DISABLE_KAFKA', '1')
    from app import create_app
    fresh_app = create_app()
    fresh_app.config['TESTING'] = True
    with fresh_app.app_context():
        c = fresh_app.test_client()
        c.post('/loginUser',
               data=json.dumps({'username': 'User_Admin', 'password': '12345'}),
               content_type='application/json')
        yield c


@pytest.fixture(scope='module')
def seeded_logs(app):
    from models import db, AuditLog
    from audit_trail import _generate_checksum

    def make_entry(**kwargs):
        e = AuditLog(**kwargs)
        e.checksum = _generate_checksum(e)
        return e

    entries = [
        make_entry(
            timestamp=datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
            username='User_Admin', action_type='LOGIN',
            record_type='USER'
        ),
        make_entry(
            timestamp=datetime(2026, 3, 1, 11, 0, 0, tzinfo=timezone.utc),
            username='User_Admin', action_type='CREATE',
            record_type='ORDER', record_id='ORD-001'
        ),
        make_entry(
            timestamp=datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc),
            username='User_Admin', action_type='UPDATE',
            record_type='ORDER', record_id='ORD-001',
            field_name='status', old_value='Created', new_value='Released'
        ),
        make_entry(
            timestamp=datetime(2026, 3, 2, 9, 30, 0, tzinfo=timezone.utc),
            username='User_Admin', action_type='LOGIN_FAILED',
            record_type='USER'
        ),
        make_entry(
            timestamp=datetime(2026, 3, 3, 8, 0, 0, tzinfo=timezone.utc),
            username='User_Admin', action_type='DELETE',
            record_type='ROLE', record_id='5',
            change_reason='Role decommissioned'
        ),
    ]
    with app.app_context():
        for e in entries:
            db.session.add(e)
        db.session.commit()
    yield
    # No teardown — immutable by 21 CFR Part 11 DB trigger


# ── Route: GET /audit/ ────────────────────────────────────────────────────────

class TestDashboardIndexRoute:

    def test_unauthenticated_redirects_to_login(self, anon_client):
        # Encodes the security intent (redirect to a login landing), not the
        # exact path: this branch redirects to /index, but the combined merge
        # resolves the competing handlers to aas's /login.  Both are accepted so
        # the test stays green on the branch and post-merge.
        resp = anon_client.get('/audit/', follow_redirects=False)
        assert resp.status_code == 302
        loc = resp.headers.get('Location', '')
        assert '/login' in loc or '/index' in loc, \
            f"unauthenticated /audit/ must redirect to a login page, got {loc!r}"

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

    def test_unauthenticated_returns_401_json(self, anon_client):
        resp = anon_client.get('/audit/api/stats')
        assert resp.status_code == 401
        assert resp.content_type.startswith('application/json')
        assert resp.get_json().get('error') == 'Authentication required'

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

    def test_unauthenticated_returns_401_json(self, anon_client):
        resp = anon_client.get('/audit/api/logs')
        assert resp.status_code == 401
        assert resp.content_type.startswith('application/json')
        assert resp.get_json().get('error') == 'Authentication required'

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

    def test_unauthenticated_returns_401_json(self, anon_client):
        resp = anon_client.get('/audit/api/integrity')
        assert resp.status_code == 401
        assert resp.content_type.startswith('application/json')
        assert resp.get_json().get('error') == 'Authentication required'

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


class TestCSVExport:

    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.get('/audit/api/logs/export')
        assert resp.status_code == 401
        assert resp.content_type.startswith('application/json')
        assert resp.get_json().get('error') == 'Authentication required'

    def test_returns_csv_content_type(self, logged_in_client, seeded_logs):
        resp = logged_in_client.get('/audit/api/logs/export?format=csv')
        assert resp.status_code == 200
        assert 'text/csv' in resp.content_type

    def test_csv_has_header_row(self, logged_in_client, seeded_logs):
        resp = logged_in_client.get('/audit/api/logs/export?format=csv')
        lines = resp.data.decode('utf-8').splitlines()
        assert lines[0] == 'id,timestamp,username,action_type,record_type,record_id,field_name,old_value,new_value,change_reason,ip_address,endpoint,checksum'

    def test_csv_contains_seeded_data(self, logged_in_client, seeded_logs):
        resp = logged_in_client.get('/audit/api/logs/export?format=csv')
        content = resp.data.decode('utf-8')
        assert 'User_Admin' in content
        assert 'LOGIN' in content

    def test_csv_filter_by_action_type(self, logged_in_client, seeded_logs):
        resp = logged_in_client.get('/audit/api/logs/export?format=csv&action_type=LOGIN')
        lines = resp.data.decode('utf-8').splitlines()
        # Every data row must be LOGIN (skip header)
        for line in lines[1:]:
            assert 'LOGIN' in line

    def test_csv_filename_in_content_disposition(self, logged_in_client, seeded_logs):
        resp = logged_in_client.get('/audit/api/logs/export?format=csv')
        assert 'attachment' in resp.headers.get('Content-Disposition', '')
        assert '.csv' in resp.headers.get('Content-Disposition', '')

    def test_csv_neutralises_formula_injection(self, app, logged_in_client):
        """A cell starting with '=' must be prefixed with ' so Excel/Sheets
        won't execute it as a formula (OWASP CSV injection)."""
        from models import db, AuditLog
        from audit_trail import _generate_checksum
        with app.app_context():
            e = AuditLog(
                timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc),
                username='x', action_type='UPDATE', record_type='ORDER',
                record_id='ORD-CSV', field_name='note', old_value='=cmd()|0',
            )
            e.checksum = _generate_checksum(e)
            db.session.add(e)
            db.session.commit()
        content = logged_in_client.get('/audit/api/logs/export?format=csv').data.decode('utf-8')
        assert "'=cmd()|0" in content, "formula cell must be neutralised with a leading quote"


# ── Behaviour: integrity tamper detection ─────────────────────────────────────

class TestIntegrityTamperDetection:

    def test_flags_tampered_row_not_clean_one(self, app, logged_in_client):
        from models import db, AuditLog
        from audit_trail import _generate_checksum
        from sqlalchemy import text

        def _seed_valid(ts):
            """Insert a row whose stored checksum matches its READ-BACK form.
            SQLite's DateTime drops tzinfo on round-trip, so the checksum must be
            computed from the reloaded row or it would falsely read as tampered.
            (Postgres timestamptz round-trips losslessly — prod is unaffected.)"""
            e = AuditLog(timestamp=ts, username='u',
                         action_type='LOGIN', record_type='USER')
            db.session.add(e)
            db.session.commit()
            db.session.refresh(e)
            e.checksum = _generate_checksum(e)
            db.session.commit()
            return e.id

        with app.app_context():
            good_id = _seed_valid(datetime(2026, 4, 1, tzinfo=timezone.utc))
            bad_id = _seed_valid(datetime(2026, 4, 2, tzinfo=timezone.utc))
            # Tamper the data AFTER its checksum was stored (raw UPDATE — SQLite
            # has no immutability trigger). Stored checksum no longer matches.
            db.session.execute(
                text("UPDATE audit_trail.audit_logs SET change_reason='TAMPERED' WHERE id=:i"),
                {'i': bad_id})
            db.session.commit()

        data = logged_in_client.get('/audit/api/integrity?limit=5000').get_json()
        assert bad_id in data['tampered_ids'], "tampered row must be detected"
        assert good_id not in data['tampered_ids'], "valid row must not be flagged"
        assert data['tampered'] >= 1

    def test_integrity_pagination(self, app, logged_in_client):
        from models import db, AuditLog
        from audit_trail import _generate_checksum
        with app.app_context():
            rows = []
            for i in range(3):
                e = AuditLog(timestamp=datetime(2026, 5, 1 + i, tzinfo=timezone.utc),
                             username='pg', action_type='LOGIN', record_type='USER')
                e.checksum = _generate_checksum(e)
                rows.append(e)
            db.session.add_all(rows)
            db.session.commit()

        first = logged_in_client.get('/audit/api/integrity?limit=1').get_json()
        assert first['has_more'] is True
        assert first['next_since_id'] is not None
        assert first['applied_limit'] == 1
        nxt = logged_in_client.get(
            f"/audit/api/integrity?limit=1&since_id={first['next_since_id']}").get_json()
        assert nxt['total_checked'] <= 1


# ── Behaviour: date-range filtering ───────────────────────────────────────────

class TestDateFilter:

    def test_filter_by_date_range(self, logged_in_client, seeded_logs):
        # seeded_logs span 2026-03-01 .. 03-03; pin to the 03-02 day.
        data = logged_in_client.get(
            '/audit/api/logs?date_from=2026-03-02&date_to=2026-03-02').get_json()
        assert data['total'] >= 1
        for e in data['logs']:
            assert e['timestamp'][:10] == '2026-03-02', e['timestamp']

    def test_invalid_date_returns_400(self, logged_in_client):
        resp = logged_in_client.get('/audit/api/logs?date_from=not-a-date')
        assert resp.status_code == 400
        assert 'date_from' in resp.get_json().get('error', '')


# ── Access control: the audit-view permission gate ────────────────────────────

class TestAccessControl:

    API_PATHS = ('/audit/api/stats', '/audit/api/logs',
                 '/audit/api/integrity', '/audit/api/logs/export')

    def test_api_without_permission_returns_403_json(self, noperm_client):
        for path in self.API_PATHS:
            resp = noperm_client.get(path)
            assert resp.status_code == 403, f"{path} should be 403 without audit-view"
            assert resp.get_json().get('error') == 'Permission required'

    def test_html_without_permission_forbidden(self, noperm_client):
        resp = noperm_client.get('/audit/')
        assert resp.status_code == 403

    def test_api_with_permission_returns_200(self, logged_in_client):
        for path in ('/audit/api/stats', '/audit/api/logs', '/audit/api/integrity'):
            assert logged_in_client.get(path).status_code == 200


# ── XSS: template escapes user-controlled audit values ────────────────────────

class TestDashboardXSS:

    def test_render_helpers_escape_output(self, logged_in_client):
        html = logged_in_client.get('/audit/').data.decode('utf-8')
        assert 'function escapeHtml' in html, "escapeHtml helper must be defined"
        assert 'escapeHtml(val)' in html, "cell() must route values through escapeHtml"


# ── UI requirements: UTC label, on-demand integrity, expandable rows ──────────

class TestDashboardUI:

    def test_timestamp_column_labelled_utc(self, logged_in_client):
        html = logged_in_client.get('/audit/').data.decode('utf-8')
        assert 'Timestamp (UTC)' in html, "timestamp column must be labelled UTC"

    def test_integrity_is_on_demand_button(self, logged_in_client):
        html = logged_in_client.get('/audit/').data.decode('utf-8')
        assert 'id="btn-verify"' in html and 'runIntegrity()' in html, \
            "integrity must be triggered by an explicit Run check button"
        assert 'Not verified' in html, "integrity card starts as 'Not verified'"

    def test_rows_are_expandable(self, logged_in_client):
        html = logged_in_client.get('/audit/').data.decode('utf-8')
        assert 'tr.expanded' in html, "expanded-row styling must be present"
        assert "toggle('expanded')" in html, "rows must toggle an expanded class on click"
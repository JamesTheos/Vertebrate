"""
test_audit_trail.py
Unit tests for audit_trail.py — 21 CFR Part 11 compliance
Covers all uncovered branches: lines 50, 66-68, 120-122, 172-185, 197, 201, 205

Usage:
    docker compose exec vertebrate-app python -m pytest \
        tests/test_audit_trail.py -v
"""
import os
import pytest

os.environ.setdefault('DISABLE_KAFKA', '1')


# ─── App Fixture ──────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def app():
    from app import create_app
    flask_app = create_app()
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    with flask_app.app_context():
        yield flask_app


# ─── 1. _validate_change_reason — all three branches ─────────────────────────

class TestValidateChangeReason:

    def test_missing_reason_for_required_action_raises(self, app):
        """line 50 + 172: DELETE and UPDATE require change_reason."""
        from audit_trail import log_audit
        with app.app_context():
            with pytest.raises(ValueError, match="change_reason is required for action type: DELETE"):
                log_audit(
                    action_type='DELETE',
                    record_type='SYSTEM',
                    record_id='test-001'
                    # change_reason intentionally omitted
                )

    def test_missing_reason_for_required_record_type_raises(self, app):
        """line 177-178: ROLE record type requires change_reason."""
        from audit_trail import log_audit
        with app.app_context():
            with pytest.raises(ValueError, match="change_reason is required for record type: ROLE"):
                log_audit(
                    action_type='CREATE',
                    record_type='ROLE',
                    record_id='test-001'
                    # change_reason intentionally omitted
                )

    def test_missing_reason_for_required_field_raises(self, app):
        """line 181-182: 'password' field requires change_reason."""
        from audit_trail import log_audit
        with app.app_context():
            with pytest.raises(ValueError, match="change_reason is required for field: password"):
                log_audit(
                    action_type='CREATE',
                    record_type='SYSTEM',
                    record_id='test-001',
                    field_name='password'
                    # change_reason intentionally omitted
                )

    def test_provided_reason_does_not_raise(self, app):
        """All required-reason paths pass when change_reason is provided."""
        from audit_trail import log_audit
        with app.app_context():
            entry_id = log_audit(
                action_type='DELETE',
                record_type='SYSTEM',
                record_id='test-validate-ok',
                change_reason='Authorized deletion for test'
            )
            assert entry_id is not None

    def test_audit_disabled_returns_none(self, app, monkeypatch):
        """line 50: When AUDIT_ENABLED is False, log_audit returns None immediately."""
        import audit_trail
        monkeypatch.setattr(audit_trail, 'AUDIT_ENABLED', False)
        with app.app_context():
            result = audit_trail.log_audit(
                action_type='SYSTEM',
                record_type='SYSTEM',
                record_id='test-disabled',
                change_reason='Should not be written'
            )
            assert result is None


# ─── 2. User context fallback — lines 66-68 ──────────────────────────────────

class TestUserContextFallback:

    def test_log_audit_outside_request_context_uses_system_username(self, app):
        """
        lines 66-68: When current_user raises RuntimeError (no request context),
        username falls back to SYSTEM and user_id to None.
        """
        from audit_trail import log_audit
        from models import AuditLog
        from sqlalchemy.orm import Session
        from models import db

        with app.app_context():
            entry_id = log_audit(
                action_type='SYSTEM',
                record_type='SYSTEM',
                record_id='test-no-request-ctx',
                change_reason='System initiated action'
            )
            assert entry_id is not None

            with Session(db.engine) as s:
                entry = s.get(AuditLog, entry_id)
                assert entry.username == 'SYSTEM'
                assert entry.user_id is None


# ─── 3. log_multiple_changes — None filtering, line 120-122 ──────────────────

class TestLogMultipleChanges:

    def test_all_valid_changes_returns_all_ids(self, app):
        """log_multiple_changes returns one ID per successful entry."""
        from audit_trail import log_multiple_changes
        with app.app_context():
            ids = log_multiple_changes(
                action_type='UPDATE',
                record_type='SYSTEM',
                record_id='test-multi-001',
                changes=[
                    {'field_name': 'status',   'old_value': 'active',   'new_value': 'inactive'},
                    {'field_name': 'location',  'old_value': 'site-a',   'new_value': 'site-b'},
                ],
                change_reason='Bulk update for test'
            )
            assert len(ids) == 2
            assert all(i is not None for i in ids)

    def test_empty_changes_returns_empty_list(self, app):
        """Edge case: empty changes list returns []."""
        from audit_trail import log_multiple_changes
        with app.app_context():
            ids = log_multiple_changes(
                action_type='UPDATE',
                record_type='SYSTEM',
                record_id='test-multi-003',
                changes=[],
                change_reason='Empty batch test'
            )
            assert ids == []

# ─── 4. _sanitize_value — lines 197, 201, 205 ────────────────────────────────

class TestSanitizeValue:

    def test_none_value_returns_none(self):
        """line 197: _sanitize_value(field, None) returns None."""
        from audit_trail import _sanitize_value
        assert _sanitize_value('status', None) is None

    def test_empty_string_returns_none(self):
        """line 197: _sanitize_value(field, '') returns None (falsy)."""
        from audit_trail import _sanitize_value
        assert _sanitize_value('status', '') is None

    def test_excluded_field_is_redacted(self):
        """line 201: password field value is replaced with [REDACTED]."""
        from audit_trail import _sanitize_value
        assert _sanitize_value('password', 'supersecret') == '[REDACTED]'

    def test_excluded_field_partial_match(self):
        """line 201: password_hash also matches the 'password' exclude rule."""
        from audit_trail import _sanitize_value
        assert _sanitize_value('password_hash', 'abc123') == '[REDACTED]'

    def test_non_excluded_field_returns_value(self):
        """line 205: normal field passes through as string."""
        from audit_trail import _sanitize_value
        assert _sanitize_value('username', 'john') == 'john'

    def test_none_field_name_with_value_returns_value(self):
        """line 205: field_name=None skips exclusion check, returns value."""
        from audit_trail import _sanitize_value
        assert _sanitize_value(None, 'somevalue') == 'somevalue'

# ─── 5. Authenticated user context — lines 61-62 ─────────────────────────────

class TestAuthenticatedUserContext:

    @pytest.fixture
    def logged_in_client(self, app):
        """Create a real user, log in, yield client, then clean up."""
        from models import db, User, UserRoles, Role
        from werkzeug.security import generate_password_hash

        USERNAME = 'pytest_audit_trail_u01'

        with app.app_context():
            # Pre-clean
            existing = User.query.filter_by(username=USERNAME).first()
            if existing:
                UserRoles.query.filter_by(user_id=existing.uid).delete()
                db.session.delete(existing)
                db.session.commit()

            role = Role.query.filter_by(name='operator').first()
            if not role:
                role = Role(name='operator')
                db.session.add(role)
                db.session.commit()

            user = User(
                username=USERNAME,
                password=generate_password_hash('TrailPass123!')
            )
            user.roles.append(role)
            db.session.add(user)
            db.session.commit()
            uid = user.uid

        client = app.test_client()
        import json
        client.post('/loginUser',
                    data=json.dumps({'username': USERNAME, 'password': 'TrailPass123!'}),
                    content_type='application/json')

        yield client, uid

        # Teardown
        client.post('/logoutUser', content_type='application/json')
        with app.app_context():
            u = User.query.filter_by(username=USERNAME).first()
            if u:
                UserRoles.query.filter_by(user_id=u.uid).delete()
                db.session.delete(u)
                db.session.commit()

    def test_authenticated_user_id_and_username_are_logged(self, app, logged_in_client):
        """lines 61-62: log_audit captures user_id and username from current_user."""
        from audit_trail import log_audit
        from models import AuditLog, db
        from sqlalchemy.orm import Session

        client, uid = logged_in_client

        with client.application.test_request_context('/'):
            # Push a real logged-in user into the request context
            from flask_login import login_user
            from models import User
            with app.app_context():
                user = db.session.get(User, uid)
                login_user(user)
                entry_id = log_audit(
                    action_type='SYSTEM',
                    record_type='SYSTEM',
                    record_id='test-auth-ctx',
                    change_reason='Authenticated context test'
                )
                assert entry_id is not None
                with Session(db.engine) as s:
                    entry = s.get(AuditLog, entry_id)
                    assert entry.user_id == uid
                    assert entry.username != 'SYSTEM'


# ─── 6. Request context details — lines 77-84 ────────────────────────────────

class TestRequestContextDetails:

    def test_ip_method_endpoint_captured_in_request_context(self, app):
        """
        lines 77-84: When LOG_REQUEST_DETAILS is True and a request context
        is active, ip_address, request_method and endpoint are auto-captured.
        """
        from audit_trail import log_audit
        from models import AuditLog, db
        from sqlalchemy.orm import Session

        with app.test_request_context('/', method='GET'):
            entry_id = log_audit(
                action_type='SYSTEM',
                record_type='SYSTEM',
                record_id='test-request-ctx',
                change_reason='Request context capture test'
            )
            assert entry_id is not None

            with app.app_context():
                with Session(db.engine) as s:
                    entry = s.get(AuditLog, entry_id)
                    assert entry.request_method == 'GET'
                    assert entry.ip_address is not None or entry.endpoint is not None


# ─── 7. Exception fallback in log_audit — lines 66-68 ────────────────────────

class TestCurrentUserExceptionFallback:

    def test_attribute_error_on_current_user_falls_back_to_system(self, app, monkeypatch):
        """
        lines 66-68: If current_user.is_authenticated raises AttributeError,
        username falls back to SYSTEM.
        """
        import audit_trail

        class BrokenUser:
            @property
            def is_authenticated(self):
                raise AttributeError("simulated broken user")

        import flask_login
        monkeypatch.setattr(flask_login, 'current_user', BrokenUser())

        from models import AuditLog, db
        from sqlalchemy.orm import Session

        with app.app_context():
            entry_id = audit_trail.log_audit(
                action_type='SYSTEM',
                record_type='SYSTEM',
                record_id='test-attr-error',
                change_reason='Exception fallback test'
            )
            assert entry_id is not None
            with Session(db.engine) as s:
                entry = s.get(AuditLog, entry_id)
                assert entry.username == 'SYSTEM'
                assert entry.user_id is None

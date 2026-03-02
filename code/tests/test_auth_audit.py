"""
test_auth_audit.py
Integration tests for auth.py audit logging — 21 CFR Part 11 compliance
Runs inside Docker against the real PostgreSQL DB.

Usage:
    docker compose exec vertebrate-app python -m pytest \
        /app/code/tests/test_auth_audit.py -v
"""
import os
import json
import pytest
from werkzeug.security import generate_password_hash

os.environ.setdefault('DISABLE_KAFKA', '1')


# ─── App & Client ─────────────────────────────────────────────────────────────

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


# ─── Test Data Fixtures ───────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def base_role(app):
    """Reuse existing 'operator' role or create one for the test module."""
    from models import db, Role
    with app.app_context():
        role = Role.query.filter_by(name='operator').first()
        if not role:
            role = Role(name='operator')
            db.session.add(role)
            db.session.commit()
        yield {'id': role.id, 'name': role.name}


def _delete_user_by_username(app, username):
    """Delete a user and their UserRoles rows. Safe to call if user not found."""
    from models import db, User, UserRoles
    with app.app_context():
        u = User.query.filter_by(username=username).first()
        if u:
            UserRoles.query.filter_by(user_id=u.uid).delete()
            db.session.delete(u)
            db.session.commit()


@pytest.fixture
def test_user(app, base_role):
    """
    Creates a fresh test user before each test, deletes it after.
    Pre-cleans any leftover from a crashed prior run.
    """
    from models import db, User, UserRoles, Role

    TEST_USERNAME = 'pytest_audit_u01'

    # ── Setup ──────────────────────────────────────────────────────────────
    with app.app_context():
        existing = User.query.filter_by(username=TEST_USERNAME).first()
        if existing:
            UserRoles.query.filter_by(user_id=existing.uid).delete()
            db.session.delete(existing)
            db.session.commit()

        role = db.session.get(Role, base_role['id'])
        user = User(
            username=TEST_USERNAME,
            password=generate_password_hash('AuditPass123!')
        )
        user.roles.append(role)
        db.session.add(user)
        db.session.commit()
        uid = user.uid

    yield {
        'id': uid,
        'username': TEST_USERNAME,
        'password': 'AuditPass123!',
        'role_id': base_role['id'],
        'role_name': base_role['name'],
    }

    # ── Teardown ───────────────────────────────────────────────────────────
    _delete_user_by_username(app, TEST_USERNAME)
    _delete_user_by_username(app, TEST_USERNAME + '_renamed')


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_latest_entry(app, action_type, record_type, record_id=None, field_name=None):
    """Return the most recent AuditLog row matching the given filters."""
    from models import AuditLog
    with app.app_context():
        q = AuditLog.query.filter_by(action_type=action_type, record_type=record_type)
        if record_id is not None:
            q = q.filter_by(record_id=str(record_id))
        if field_name is not None:
            q = q.filter_by(field_name=field_name)
        return q.order_by(AuditLog.id.desc()).first()


def login(client, username, password):
    """Log out any existing session then log in fresh."""
    client.post('/logoutUser', content_type='application/json')
    return client.post(
        '/loginUser',
        data=json.dumps({'username': username, 'password': password}),
        content_type='application/json'
    )


# ─── 1. Registration ──────────────────────────────────────────────────────────

class TestRegistrationAudit:

    def test_new_user_creates_create_entry(self, app, client, base_role):
        from models import db, User, UserRoles
        TMP = 'pytest_reg_tmp'
        _delete_user_by_username(app, TMP)
        try:
            r = client.post('/registerUser',
                            data=json.dumps({'username': TMP,
                                             'password': 'Reg123!',
                                             'roles': [base_role['id']]}),
                            content_type='application/json')
            assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.data}"

            with app.app_context():
                user = User.query.filter_by(username=TMP).first()
            assert user is not None, "User not found in DB after registration"

            entry = get_latest_entry(app, 'CREATE', 'USER', user.uid)
            assert entry is not None,          "CREATE audit entry missing"
            assert entry.change_reason == 'New user registration'
            assert entry.checksum is not None, "Checksum must not be NULL"

        finally:
            _delete_user_by_username(app, TMP)

    def test_rejected_registration_writes_no_create_entry(self, app, client,
                                                           test_user, base_role):
        from models import AuditLog
        with app.app_context():
            before = AuditLog.query.filter_by(action_type='CREATE',
                                              record_type='USER').count()
        client.post('/registerUser',
                    data=json.dumps({'username': test_user['username'],
                                     'password': 'x',
                                     'roles': [base_role['id']]}),
                    content_type='application/json')
        with app.app_context():
            after = AuditLog.query.filter_by(action_type='CREATE',
                                             record_type='USER').count()
        assert after == before, "Spurious CREATE entry written for a rejected registration"


# ─── 2. Login ─────────────────────────────────────────────────────────────────

class TestLoginAudit:

    def test_successful_login_creates_login_entry(self, app, client, test_user):
        login(client, test_user['username'], test_user['password'])
        entry = get_latest_entry(app, 'LOGIN', 'USER', test_user['id'])
        assert entry is not None,                        "LOGIN audit entry missing"
        assert entry.record_id == str(test_user['id'])
        assert entry.change_reason == 'Successful login'
        assert entry.checksum is not None,               "Checksum must not be NULL"
        client.post('/logoutUser', content_type='application/json')

    def test_wrong_password_creates_login_failed_entry(self, app, client, test_user):
        from models import AuditLog
        with app.app_context():
            before = AuditLog.query.filter_by(
                action_type='LOGIN_FAILED', record_id=str(test_user['id'])).count()
        login(client, test_user['username'], 'WrongPassword!')
        with app.app_context():
            after = AuditLog.query.filter_by(
                action_type='LOGIN_FAILED', record_id=str(test_user['id'])).count()
        assert after > before, "LOGIN_FAILED entry missing for wrong password"

    def test_unknown_username_creates_login_failed_entry(self, app, client):
        from models import AuditLog
        with app.app_context():
            before = AuditLog.query.filter_by(action_type='LOGIN_FAILED').count()
        login(client, 'ghost_user_nobody_xyz99', 'anything')
        with app.app_context():
            after = AuditLog.query.filter_by(action_type='LOGIN_FAILED').count()
        assert after > before, "LOGIN_FAILED entry missing for unknown username"


# ─── 3. Logout ────────────────────────────────────────────────────────────────

class TestLogoutAudit:

    def test_logout_creates_logout_entry(self, app, client, test_user):
        login(client, test_user['username'], test_user['password'])
        client.post('/logoutUser', content_type='application/json')
        entry = get_latest_entry(app, 'LOGOUT', 'USER', test_user['id'])
        assert entry is not None,                       "LOGOUT audit entry missing"
        assert entry.record_id == str(test_user['id'])
        assert entry.change_reason == 'User logout'
        assert entry.checksum is not None,              "Checksum must not be NULL"


# ─── 4. UpdateUser ────────────────────────────────────────────────────────────

class TestUpdateUserAudit:

    def test_password_change_is_redacted(self, app, client, test_user):
        login(client, test_user['username'], test_user['password'])
        client.post('/UpdateUser',
                    data=json.dumps({'password': 'NewSecure456!'}),
                    content_type='application/json')
        entry = get_latest_entry(app, 'UPDATE', 'USER',
                                 test_user['id'], field_name='password')
        assert entry is not None, "Password UPDATE entry missing"
        assert entry.old_value == "[REDACTED]", f"old_value should be [REDACTED], got: {entry.old_value}"
        assert entry.new_value == "[REDACTED]", f"new_value should be [REDACTED], got: {entry.new_value}"
        assert entry.change_reason == 'User password change'
        assert entry.checksum is not None
        client.post('/logoutUser', content_type='application/json')

    def test_username_change_logs_old_and_new_values(self, app, client, test_user):
        from models import db, User
        login(client, test_user['username'], test_user['password'])
        new_name = test_user['username'] + '_renamed'
        client.post('/UpdateUser',
                    data=json.dumps({'username': new_name}),
                    content_type='application/json')
        entry = get_latest_entry(app, 'UPDATE', 'USER',
                                 test_user['id'], field_name='username')
        assert entry is not None, "Username UPDATE entry missing"
        assert entry.old_value == test_user['username']
        assert entry.new_value == new_name
        assert entry.change_reason == 'Username updated'
        with app.app_context():
            u = db.session.get(User, test_user['id'])
            if u:
                u.username = test_user['username']
                db.session.commit()
        client.post('/logoutUser', content_type='application/json')

    def test_role_change_logs_old_and_new_role_names(self, app, client, test_user):
        from models import db, Role
        login(client, test_user['username'], test_user['password'])
        with app.app_context():
            admin = Role.query.filter_by(name='admin').first()
            if not admin:
                admin = Role(name='admin')
                db.session.add(admin)
                db.session.commit()
            admin_id = admin.id
        client.post('/UpdateUser',
                    data=json.dumps({'roles': [admin_id]}),
                    content_type='application/json')
        entry = get_latest_entry(app, 'UPDATE', 'USER',
                                 test_user['id'], field_name='role')
        assert entry is not None, "Role UPDATE entry missing"
        assert test_user['role_name'] in entry.old_value, f"Expected old role in old_value: {entry.old_value}"
        assert 'admin' in entry.new_value, f"Expected admin in new_value: {entry.new_value}"
        assert entry.change_reason == 'Role updated by admin'
        assert entry.checksum is not None
        client.post('/logoutUser', content_type='application/json')


# ─── 5. Checksum Integrity ────────────────────────────────────────────────────

class TestChecksumIntegrity:

    def test_every_audit_entry_for_test_user_has_a_checksum(self, app, client,
                                                             test_user):
        """Every entry must have a non-null checksum — required for tamper evidence."""
        from models import AuditLog
        login(client, test_user['username'], test_user['password'])
        client.post('/logoutUser', content_type='application/json')
        with app.app_context():
            entries = AuditLog.query.filter_by(
                record_type='USER', record_id=str(test_user['id'])
            ).all()
        assert len(entries) > 0, "No audit entries found — did earlier tests run?"
        missing = [e.id for e in entries if e.checksum is None]
        assert not missing, f"Entries without checksum (IDs): {missing}"

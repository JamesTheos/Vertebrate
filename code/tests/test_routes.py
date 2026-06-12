"""
test_routes.py — TDD suite for every route registered in app.py.

Coverage strategy:
  - Unauthenticated access to @login_required routes → 302 to /login
  - Authenticated access to page routes → 200
  - Auth endpoints (register / login / logout) → correct redirects & DB state
  - User-management CRUD (add / delete / update / get) → JSON responses & DB state
  - Role management (define_role / update_role) → JSON responses & DB state
  - Permission check endpoint → correct True/False logic
  - /index alias → same as /
  - Public routes (login-error, logout-message, subscription-denied) → 200
  - SCADA data + plant config routes → 200 with correct type

No Kafka, no external DB needed — conftest wires SQLite in-memory + DISABLE_KAFKA=1.
"""

import pytest
from werkzeug.security import generate_password_hash
from models import db as _db, User, Role, RolePermission, Permission, Subscriptions


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _seed_user(app, username='testuser', password='testpass', role_name='Admin'):
    """Create a user with a role inside an app context."""
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name)
            _db.session.add(role)
            _db.session.flush()
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, password=generate_password_hash(password))
            user.roles.append(role)
            _db.session.add(user)
            _db.session.commit()
        return user.uid, role.id


def _login(client, username='testuser', password='testpass'):
    """POST /loginUser and return response."""
    import json
    return client.post(
        '/loginUser',
        data=json.dumps({'username': username, 'password': password}),
        content_type='application/json'
    )


def _logout(client):
    return client.post('/logoutUser', content_type='application/json')


def _seed_aas_subscription(app):
    """Activate the 'aas' subscription in the DB."""
    with app.app_context():
        sub = Subscriptions.query.filter_by(apps='aas').first()
        if not sub:
            _db.session.add(Subscriptions(apps='aas', subscribed=True))
            _db.session.commit()


def _seed_aas_permission(app, role_name='Admin'):
    """Add the aas_export permission key to the named role."""
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            return
        perm = Permission.query.filter_by(key='aas_export').first()
        if not perm:
            perm = Permission(key='aas_export')
            _db.session.add(perm)
            _db.session.flush()
        if not RolePermission.query.filter_by(role_id=role.id, permission_id=perm.id).first():
            _db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
            _db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_db(app):
    """Wipe users/roles/permissions/subscriptions before every test for isolation."""
    with app.app_context():
        import sqlalchemy as sa
        RolePermission.query.delete()
        Permission.query.delete()
        _db.session.execute(sa.text('DELETE FROM user_roles'))
        User.query.delete()
        Role.query.delete()
        Subscriptions.query.delete()
        _db.session.commit()
    yield


@pytest.fixture()
def auth_client(app, client):
    """A test client that is already logged in as testuser/Admin."""
    _seed_user(app)
    _login(client)
    return client


# ─────────────────────────────────────────────────────────────────────────────
# 1. Public routes — no login required
# ─────────────────────────────────────────────────────────────────────────────

class TestPublicRoutes:
    def test_login_page_get(self, client):
        r = client.get('/login')
        assert r.status_code == 200

    def test_login_error_page(self, client):
        r = client.get('/login-error')
        assert r.status_code == 200

    def test_logout_message_page(self, client):
        r = client.get('/logout-message')
        assert r.status_code == 200

    def test_subscription_denied_page(self, client):
        r = client.get('/subscription-denied')
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 2. @login_required routes redirect when unauthenticated
# ─────────────────────────────────────────────────────────────────────────────

class TestLoginRequired:
    PROTECTED = [
        '/', '/index', '/settings', '/basesettings',
        '/user-management', '/role-management', '/user-profile',
        '/subscription-management', '/equipment-overview',
        '/workflow-overview', '/sampling', '/batch',
        '/get-users', '/get-user-data', '/get-user-role',
        '/aas-viewer',
    ]

    def test_protected_routes_redirect_to_login(self, client):
        for path in self.PROTECTED:
            r = client.get(path, follow_redirects=False)
            assert r.status_code in (302, 308), (
                f"{path} expected redirect, got {r.status_code}"
            )
            location = r.headers.get('Location', '')
            assert 'login' in location.lower(), (
                f"{path} redirect location '{location}' does not point to /login"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 2b. AAS API routes — must also redirect unauthenticated callers to login
# ─────────────────────────────────────────────────────────────────────────────

class TestAasApiAuth:
    """
    The AAS API endpoints are called directly by JS and external M2M clients.
    Without @login_required they are publicly accessible — this class enforces
    that both routes redirect to /login when there is no active session.
    """
    API_ROUTES = [
        '/api/aas/equipment/filling-machine-1',
        '/api/aas/export/equipment/filling-machine-1',
    ]

    def test_unauthenticated_requests_redirect_to_login(self, client):
        for path in self.API_ROUTES:
            r = client.get(path, follow_redirects=False)
            assert r.status_code in (302, 308), (
                f"{path} expected redirect for unauthenticated request, got {r.status_code}"
            )
            location = r.headers.get('Location', '')
            assert 'login' in location.lower(), (
                f"{path} redirect location '{location}' does not point to /login"
            )

    def test_authenticated_subscribed_permitted_requests_return_200(self, app, client):
        _seed_user(app)
        _login(client)
        _seed_aas_subscription(app)
        _seed_aas_permission(app)
        for path in self.API_ROUTES:
            r = client.get(path, follow_redirects=False)
            assert r.status_code == 200, (
                f"{path} expected 200 for fully-authorised request, got {r.status_code}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 2c. AAS three-layer access control (subscription + permission)
# ─────────────────────────────────────────────────────────────────────────────

class TestAasAccessControl:
    """
    Verifies the full three-layer guard on AAS routes:
      1. @login_required         — covered by TestLoginRequired / TestAasApiAuth
      2. @check_subscription     — unsubscribed user sees the access-denied page
      3. @permission_required    — subscribed but unpermitted user gets 403
    """

    def test_unsubscribed_viewer_shows_access_denied(self, app, client):
        _seed_user(app)
        _login(client)
        # No subscription seeded — check_subscription should block
        r = client.get('/aas-viewer')
        assert b'Access denied' in r.data

    def test_unsubscribed_api_does_not_return_aas_json(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.get('/api/aas/equipment/filling-machine-1')
        assert 'application/json' not in r.content_type

    def test_subscribed_no_permission_returns_403(self, app, client):
        _seed_user(app)
        _login(client)
        _seed_aas_subscription(app)
        # Admin role exists but has no aas_export permission yet
        r = client.get('/api/aas/equipment/filling-machine-1')
        assert r.status_code == 403

    def test_subscribed_with_permission_returns_200(self, app, client):
        _seed_user(app)
        _login(client)
        _seed_aas_subscription(app)
        _seed_aas_permission(app)
        r = client.get('/api/aas/equipment/filling-machine-1')
        assert r.status_code == 200
        assert r.get_json() is not None


# ─────────────────────────────────────────────────────────────────────────────
# 3. /index alias
# ─────────────────────────────────────────────────────────────────────────────

class TestIndexAlias:
    def test_slash_and_index_both_redirect_when_unauthed(self, client):
        for path in ('/', '/index'):
            r = client.get(path, follow_redirects=False)
            assert r.status_code in (302, 308), f"{path} should redirect unauthenticated user"

    def test_index_returns_200_when_authenticated(self, app, client):
        _seed_user(app)
        _login(client)
        for path in ('/', '/index'):
            r = client.get(path)
            assert r.status_code == 200, f"{path} should be 200 when logged in"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Auth — register / login / logout
# ─────────────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_register_creates_user(self, app, client):
        with app.app_context():
            role = Role(name='Tester')
            _db.session.add(role)
            _db.session.commit()
            role_id = role.id

        r = client.post('/registerUser', json={
            'username': 'newuser',
            'password': 'secret',
            'roles': [role_id]
        })
        assert r.status_code == 201
        with app.app_context():
            assert User.query.filter_by(username='newuser').first() is not None

    def test_register_duplicate_returns_400(self, app, client):
        _seed_user(app, username='dupuser')
        with app.app_context():
            role = Role.query.first()
            role_id = role.id
        r = client.post('/registerUser', json={
            'username': 'dupuser', 'password': 'x', 'roles': [role_id]
        })
        assert r.status_code == 400

    def test_login_success_redirects_to_index(self, app, client):
        _seed_user(app)
        r = _login(client)
        data = r.get_json()
        assert r.status_code == 200
        assert 'redirect' in data
        assert data['redirect'].rstrip('/') in ('', '/index', '/')

    def test_login_wrong_password_redirects_to_error(self, app, client):
        _seed_user(app)
        r = client.post('/loginUser', json={'username': 'testuser', 'password': 'wrong'})
        data = r.get_json()
        assert 'redirect' in data
        assert 'error' in data['redirect'] or 'login' in data['redirect']

    def test_login_unknown_user_redirects_to_error(self, client):
        r = client.post('/loginUser', json={'username': 'ghost', 'password': 'x'})
        data = r.get_json()
        assert 'redirect' in data
        assert 'error' in data['redirect'] or 'login' in data['redirect']

    def test_logout_clears_session(self, app, client):
        _seed_user(app)
        _login(client)
        r = _logout(client)
        assert r.status_code == 200
        # After logout / should redirect to login
        r2 = client.get('/', follow_redirects=False)
        assert r2.status_code in (302, 308)


# ─────────────────────────────────────────────────────────────────────────────
# 5. User management routes
# ─────────────────────────────────────────────────────────────────────────────

class TestUserManagement:
    def test_get_users_returns_list(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.get('/get-users')
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)
        assert any(u['username'] == 'testuser' for u in data)

    def test_get_user_data_returns_current_user(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.get('/get-user-data')
        assert r.status_code == 200
        data = r.get_json()
        assert data['username'] == 'testuser'
        assert isinstance(data['role'], list)

    def test_get_user_role_returns_list(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.get('/get-user-role')
        assert r.status_code == 200
        data = r.get_json()
        assert 'role' in data
        assert isinstance(data['role'], list)

    def test_add_user_creates_new_user(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.post('/add-user', json={
            'username': 'brandnew',
            'password': 'pw123',
            'role': 'Admin'
        })
        assert r.status_code == 200
        assert b'successfully' in r.data.lower()
        with app.app_context():
            assert User.query.filter_by(username='brandnew').first() is not None

    def test_add_user_duplicate_returns_400(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.post('/add-user', json={
            'username': 'testuser', 'password': 'pw', 'role': 'Admin'
        })
        assert r.status_code == 400

    def test_add_user_missing_fields_returns_400(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.post('/add-user', json={'username': 'nopass'})
        assert r.status_code == 400

    def test_delete_user_removes_from_db(self, app, client):
        _seed_user(app)
        _seed_user(app, username='todelete', password='pw')
        _login(client)
        r = client.delete('/delete-user', json={'username': 'todelete'})
        assert r.status_code == 200
        with app.app_context():
            assert User.query.filter_by(username='todelete').first() is None

    def test_delete_nonexistent_user_returns_404(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.delete('/delete-user', json={'username': 'ghost'})
        assert r.status_code == 404

    def test_update_user_password(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.post('/update-user', json={
            'username': 'testuser',
            'new_password': 'newpass'
        })
        assert r.status_code == 200
        # Confirm new password works
        _logout(client)
        r2 = _login(client, password='newpass')
        data = r2.get_json()
        assert 'redirect' in data and 'error' not in data['redirect']

    def test_update_nonexistent_user_returns_404(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.post('/update-user', json={
            'username': 'nobody', 'new_password': 'x'
        })
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 6. Role management routes
# ─────────────────────────────────────────────────────────────────────────────

class TestRoleManagement:
    def test_define_role_creates_role_and_permissions(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.post('/get-role', json={
            'created_role': 'Operator',
            'role_apps': ['scada', 'manufacturing_orders']
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data['role_id'] is not None
        assert set(data['permissions']) == {'scada', 'manufacturing_orders'}
        with app.app_context():
            assert Role.query.filter_by(name='Operator').first() is not None

    def test_define_role_updates_existing_role(self, app, client):
        _seed_user(app)
        _login(client)
        client.post('/get-role', json={
            'created_role': 'Operator', 'role_apps': ['scada']
        })
        r = client.post('/get-role', json={
            'created_role': 'Operator', 'role_apps': ['manufacturing_orders']
        })
        assert r.status_code == 200
        assert r.get_json()['permissions'] == ['manufacturing_orders']

    def test_define_role_missing_fields_returns_400(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.post('/get-role', json={'created_role': 'EmptyRole'})
        assert r.status_code == 400

    def test_update_role_changes_permissions(self, app, client):
        _seed_user(app)
        _login(client)
        client.post('/get-role', json={
            'created_role': 'QA', 'role_apps': ['scada', 'order_management']
        })
        r = client.post('/update-role', json={
            'role_name': 'QA',
            'updated_role_apps': ['manufacturing_orders']
        })
        assert r.status_code == 200
        assert r.get_json()['permissions'] == ['manufacturing_orders']

    def test_update_nonexistent_role_returns_404(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.post('/update-role', json={
            'role_name': 'Ghost', 'updated_role_apps': ['scada']
        })
        assert r.status_code == 404

    def test_update_role_missing_fields_returns_400(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.post('/update-role', json={'role_name': 'Admin'})
        assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# 7. Permission check
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckPermission:
    def _setup_user_with_perm(self, app, client, perm_key='scada'):
        with app.app_context():
            role = Role(name='PermRole')
            _db.session.add(role)
            _db.session.flush()
            perm = Permission(key=perm_key)
            _db.session.add(perm)
            _db.session.flush()
            _db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
            user = User(username='permuser', password=generate_password_hash('pw'))
            user.roles.append(role)
            _db.session.add(user)
            _db.session.commit()
        _login(client, username='permuser', password='pw')

    def test_has_permission_returns_true(self, app, client):
        self._setup_user_with_perm(app, client, 'scada')
        r = client.get('/check-permission?key=scada')
        assert r.status_code == 200
        assert r.get_json()['has_permission'] is True

    def test_missing_permission_returns_false(self, app, client):
        self._setup_user_with_perm(app, client, 'scada')
        r = client.get('/check-permission?key=manufacturing_orders')
        assert r.status_code in (200, 404)
        data = r.get_json()
        assert data.get('has_permission', False) is False

    def test_no_key_returns_400(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.get('/check-permission')
        assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# 8. Authenticated page routes (templates must exist in app context)
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthenticatedPages:
    PAGES = [
        '/settings', '/basesettings', '/user-management',
        '/role-management', '/user-profile', '/subscription-management',
    ]

    def test_pages_return_200_when_logged_in(self, app, client):
        _seed_user(app)
        _login(client)
        for path in self.PAGES:
            r = client.get(path)
            assert r.status_code == 200, f"{path} returned {r.status_code} when logged in"


# ─────────────────────────────────────────────────────────────────────────────
# 9. SCADA / data routes (Kafka-free: test HTTP layer only)
# ─────────────────────────────────────────────────────────────────────────────

class TestScadaDataRoutes:
    def test_get_data_returns_list(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.get('/get-data?topic=ISPEMTemp')
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

    def test_send_data_returns_200(self, app, client):
        """Kafka producer is None in tests — route should still return 200."""
        _seed_user(app)
        _login(client)
        r = client.post('/send-data', json={'topic': 'ISPEMTemp', 'value': 42})
        assert r.status_code == 200

    def test_get_manufacturing_orders_returns_list(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.get('/get-manufacturing-orders')
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)


# ─────────────────────────────────────────────────────────────────────────────
# 10. Plant config route
# ─────────────────────────────────────────────────────────────────────────────

class TestPlantConfig:
    def test_get_plant_config_returns_dict_with_enterprise(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.get('/get-plant-config')
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, dict)
        assert 'enterprise' in data

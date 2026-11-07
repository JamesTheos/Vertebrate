"""
test_routes.py — TDD suite for every route registered in app.py.

Coverage strategy:
  - Unauthenticated access to @login_required routes → 302 to Home (/index)
  - Authenticated access to unguarded page routes → 200
  - Subscription + permission guards (AAS, orders) → "not activated" page / 403 / 200
  - Auth endpoints (register / login / logout) → correct redirects & DB state
  - Role management (define_role / update_role) → JSON responses & DB state
  - / and /index → Home, public
  - Public routes (login, login-error, logout-message) → 200
  - SCADA data route → 200 with a list

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


def _grant(app, app_name, perm_key, role_name='Admin'):
    """Enable a subscription `app_name` and grant `perm_key` to `role_name`."""
    with app.app_context():
        if not Subscriptions.query.filter_by(apps=app_name).first():
            _db.session.add(Subscriptions(apps=app_name, subscribed=True))
        role = Role.query.filter_by(name=role_name).first()
        perm = Permission.query.filter_by(key=perm_key).first()
        if not perm:
            perm = Permission(key=perm_key)
            _db.session.add(perm)
            _db.session.flush()
        if role and not RolePermission.query.filter_by(role_id=role.id, permission_id=perm.id).first():
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


# ─────────────────────────────────────────────────────────────────────────────
# 2. @login_required pages send guests to Home (which asks them to log in)
# ─────────────────────────────────────────────────────────────────────────────

class TestLoginRequired:
    # main keeps most pages public and guards them with subscription + permission
    # (guests get 403); only these use @login_required
    PROTECTED = ['/aas-viewer', '/audit/']

    def test_protected_routes_redirect_to_home(self, client):
        for path in self.PROTECTED:
            r = client.get(path, follow_redirects=False)
            assert r.status_code in (302, 308), (
                f"{path} expected redirect, got {r.status_code}"
            )
            location = r.headers.get('Location', '')
            assert location.endswith('/index'), (
                f"{path} redirect location '{location}' does not point to Home (/index)"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 2b. AAS API routes — must also redirect unauthenticated callers to login
# ─────────────────────────────────────────────────────────────────────────────

class TestAasApiAuth:
    """
    The AAS API endpoints are called directly by JS (the AAS viewer) and external
    M2M clients.  When there is no active session they must answer with a JSON
    401 — not an HTML redirect to /login — so an XHR caller can surface a clean
    "session expired" message instead of choking on "<!DOCTYPE …" when it parses
    the body as JSON.
    """
    API_ROUTES = [
        '/api/aas/equipment/filling-machine-1',
        '/api/aas/export/equipment/filling-machine-1',
        '/api/aas/export-aasx/equipment/filling-machine-1',
    ]

    def test_unauthenticated_api_requests_return_401_json(self, client):
        for path in self.API_ROUTES:
            r = client.get(path, follow_redirects=False)
            assert r.status_code == 401, (
                f"{path} expected 401 for unauthenticated request, got {r.status_code}"
            )
            assert r.is_json, (
                f"{path} 401 body must be JSON, got content-type {r.content_type}"
            )
            assert 'error' in r.get_json(), f"{path} 401 JSON missing 'error' key"

    def test_timed_out_api_request_returns_401_json(self, app, client):
        """A session that has crossed the inactivity timeout must get a JSON 401
        on /api/ routes (not a 302 redirect to /logout-message)."""
        from datetime import datetime, timedelta, UTC
        _seed_user(app)
        _login(client)
        with client.session_transaction() as sess:
            sess['last_activity'] = (datetime.now(UTC) - timedelta(seconds=600)).isoformat()
        r = client.get(self.API_ROUTES[0], follow_redirects=False)
        assert r.status_code == 401, f"expected 401 on timed-out API request, got {r.status_code}"
        assert r.is_json and 'error' in r.get_json()

    def test_timed_out_html_request_still_redirects(self, app, client):
        """Non-API (HTML) routes keep redirecting a timed-out user — only the
        response format for /api/ changes."""
        from datetime import datetime, timedelta, UTC
        _seed_user(app)
        _login(client)
        with client.session_transaction() as sess:
            sess['last_activity'] = (datetime.now(UTC) - timedelta(seconds=600)).isoformat()
        r = client.get('/aas-viewer', follow_redirects=False)
        assert r.status_code in (302, 308)
        location = r.headers.get('Location', '').lower()
        assert 'logout' in location or 'login' in location

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
      2. @check_subscription     — unsubscribed user sees the "not activated" page
      3. @permission_required    — subscribed but unpermitted user gets 403
    """

    def test_unsubscribed_viewer_shows_access_denied(self, app, client):
        _seed_user(app)
        _login(client)
        # No subscription seeded — check_subscription should block
        r = client.get('/aas-viewer')
        assert b'This module is not activated.' in r.data

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

    def test_unsubscribed_aasx_does_not_return_binary(self, app, client):
        _seed_user(app)
        _login(client)
        # No subscription — check_subscription should block before binary is produced
        r = client.get('/api/aas/export-aasx/equipment/filling-machine-1')
        assert 'application/asset-administration-shell' not in r.content_type

    def test_subscribed_no_permission_aasx_returns_403(self, app, client):
        _seed_user(app)
        _login(client)
        _seed_aas_subscription(app)
        # Admin role has no aas_export permission
        r = client.get('/api/aas/export-aasx/equipment/filling-machine-1')
        assert r.status_code == 403

    def test_unsubscribed_sync_does_not_push(self, app, client):
        _seed_user(app)
        _login(client)
        # No subscription — check_subscription renders the access-denied page
        # (HTML) instead of running the sync, so the response is never AAS JSON.
        r = client.post('/api/aas/sync/equipment/filling-machine-1')
        assert 'application/json' not in r.content_type

    def test_subscribed_no_permission_sync_returns_403(self, app, client):
        _seed_user(app)
        _login(client)
        _seed_aas_subscription(app)
        # Admin role has no aas_export permission
        r = client.post('/api/aas/sync/equipment/filling-machine-1')
        assert r.status_code == 403

    def test_subscribed_with_permission_sync_passes_guards(self, app, client):
        _seed_user(app)
        _login(client)
        _seed_aas_subscription(app)
        _seed_aas_permission(app)
        # All three guards pass → the route runs sync_to_basyx and returns its
        # status dict.  The exact status (synced/skipped/error) depends on
        # whether a BaSyx server is reachable in the runtime, so assert only
        # that the guards let the request through to a JSON status response.
        r = client.post('/api/aas/sync/equipment/filling-machine-1')
        assert r.status_code not in (401, 403, 404)
        body = r.get_json()
        assert body is not None and 'status' in body


# ─────────────────────────────────────────────────────────────────────────────
# 2c. check_subscription — bare (callable-passed-directly) form
#     The explicit @check_subscription('aas') form is covered above; the bare
#     form (used on /scada, /manufacturing-orders, /order-management) derives the
#     app name from the view's __name__. These pin both its deny and pass paths.
# ─────────────────────────────────────────────────────────────────────────────

class TestBareCheckSubscription:
    # No route on main uses the bare form, so the decorator is tested directly.
    @staticmethod
    def _bare_view():
        from subscriptions import check_subscription

        @check_subscription
        def bare_test_app():
            return 'allowed'
        return bare_test_app

    def test_bare_form_denies_when_unsubscribed(self, app):
        with app.test_request_context('/'):
            assert 'This module is not activated.' in self._bare_view()()

    def test_bare_form_allows_when_subscribed(self, app):
        # the bare form takes the subscription name from the view function's name
        with app.app_context():
            _db.session.add(Subscriptions(apps='bare_test_app', subscribed=True))
            _db.session.commit()
        with app.test_request_context('/'):
            assert self._bare_view()() == 'allowed'


# ─────────────────────────────────────────────────────────────────────────────
# 2d. subscription_management POST — upsert branches
#     test_aas_reachability covers create-new + subscribed=True; these pin the
#     two untested branches: updating an existing row, and the not_subscribed
#     (subscribed=False) path.
# ─────────────────────────────────────────────────────────────────────────────

class TestSubscriptionManagementUpsert:
    def test_not_subscribed_disables_existing_row(self, app, client):
        _seed_user(app)
        _login(client)
        with app.app_context():
            _db.session.add(Subscriptions(apps='aas', subscribed=True))
            _db.session.commit()
        import json
        r = client.post(
            '/subscription-management',
            data=json.dumps({'subscribed': [], 'not_subscribed': ['aas']}),
            content_type='application/json',
        )
        assert r.status_code == 200
        with app.app_context():
            sub = Subscriptions.query.filter_by(apps='aas').first()
            assert sub is not None and sub.subscribed is False

    def test_subscribed_flips_existing_disabled_row(self, app, client):
        _seed_user(app)
        _login(client)
        with app.app_context():
            _db.session.add(Subscriptions(apps='aas', subscribed=False))
            _db.session.commit()
        import json
        r = client.post(
            '/subscription-management',
            data=json.dumps({'subscribed': ['aas'], 'not_subscribed': []}),
            content_type='application/json',
        )
        assert r.status_code == 200
        with app.app_context():
            sub = Subscriptions.query.filter_by(apps='aas').first()
            assert sub is not None and sub.subscribed is True


# ─────────────────────────────────────────────────────────────────────────────
# 2e. Fully-authorized page routes behind the three-layer guard return 200
# ─────────────────────────────────────────────────────────────────────────────

class TestGuardedPagesAllow:
    def test_login_redirects_when_already_authenticated(self, app, client):
        _seed_user(app)
        _login(client)
        r = client.get('/login', follow_redirects=False)
        assert r.status_code == 302
        assert '/index' in r.headers.get('Location', '') or r.headers.get('Location', '').endswith('/')

    def test_aas_viewer_renders_when_subscribed_and_permitted(self, app, client):
        _seed_user(app)
        _login(client)
        _seed_aas_subscription(app)
        _seed_aas_permission(app)
        r = client.get('/aas-viewer')
        assert r.status_code == 200
        assert b'This module is not activated.' not in r.data

    def test_manufacturing_orders_page_renders_when_authorized(self, app, client):
        _seed_user(app)
        _login(client)
        _grant(app, 'manufacturing-orders', 'manufacturing-orders')
        r = client.get('/manufacturing-orders')
        assert r.status_code == 200
        assert b'This module is not activated.' not in r.data

    def test_order_management_page_renders_when_authorized(self, app, client):
        _seed_user(app)
        _login(client)
        _grant(app, 'order-management', 'order-management')
        r = client.get('/order-management')
        assert r.status_code == 200
        assert b'This module is not activated.' not in r.data


# ─────────────────────────────────────────────────────────────────────────────
# 2f. order-management POST — action branches
# ─────────────────────────────────────────────────────────────────────────────

class TestOrderManagementAction:
    WORKFLOW = 'FluVaccineISPE'

    @pytest.fixture(autouse=True)
    def authorized(self, app, client):
        _seed_user(app)
        _login(client)
        _grant(app, 'order-management', 'order-management')

    def test_missing_fields_returns_400(self, client):
        r = client.post('/order-management', json={'action': 'release'})
        assert r.status_code == 400

    def test_unknown_order_returns_404(self, client):
        r = client.post('/order-management',
                        json={'action': 'release', 'order_id': 'NOPE-999', 'workflowName': self.WORKFLOW})
        assert r.status_code == 404

    def test_unknown_action_returns_400(self, client):
        from app import data_store
        data_store['manufacturing_orders'].append(
            {'orderNumber': 'OM-1', 'product': 'P', 'status': 'Created'})
        try:
            r = client.post('/order-management',
                            json={'action': 'frobnicate', 'order_id': 'OM-1', 'workflowName': self.WORKFLOW})
            assert r.status_code == 400
        finally:
            data_store['manufacturing_orders'].clear()

    def test_release_updates_status(self, client):
        from app import data_store
        data_store['manufacturing_orders'].append(
            {'orderNumber': 'OM-2', 'product': 'P', 'status': 'Created'})
        try:
            r = client.post('/order-management',
                            json={'action': 'release', 'order_id': 'OM-2', 'workflowName': self.WORKFLOW})
            assert r.status_code == 200
            assert data_store['manufacturing_orders'][-1]['status'] == 'Released'
        finally:
            data_store['manufacturing_orders'].clear()


# ─────────────────────────────────────────────────────────────────────────────
# 3. / and /index — Home is public (guests see "Please log in")
# ─────────────────────────────────────────────────────────────────────────────

class TestIndexAlias:
    def test_slash_and_index_both_open_for_guests(self, client):
        for path in ('/', '/index'):
            r = client.get(path, follow_redirects=False)
            assert r.status_code == 200, f"{path} should show Home to a guest"

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
        # After logout a @login_required page redirects again
        r2 = client.get('/aas-viewer', follow_redirects=False)
        assert r2.status_code in (302, 308)


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
# 8. Authenticated page routes (templates must exist in app context)
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthenticatedPages:
    # pages without a subscription/permission guard (the guarded ones: test_demo_pages.py)
    PAGES = [
        '/settings', '/user-profile', '/subscription-management',
        '/updated-user', '/login-error', '/logout-message',
    ]

    def test_pages_return_200_when_logged_in(self, app, client):
        _seed_user(app)
        _login(client)
        for path in self.PAGES:
            r = client.get(path)
            assert r.status_code == 200, f"{path} returned {r.status_code} when logged in"


# ─────────────────────────────────────────────────────────────────────────────
# 9. SCADA data route (Kafka-free: test HTTP layer only)
# ─────────────────────────────────────────────────────────────────────────────

class TestScadaDataRoutes:
    def test_data_returns_list(self, client):
        r = client.get('/data/ISPEMTemp')
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

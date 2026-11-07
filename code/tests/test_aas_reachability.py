"""
test_aas_reachability.py

The AAS feature was unreachable in a fresh deploy: the `aas` subscription was
absent from both the seed list (createDB._seed_subscriptions) and the
subscription-management UI list (app.py), and the management template had no
toggle for it — so an admin had no way to enable it.

These tests guard the end-to-end reachability path:
  - `aas` is in the single shared app registry,
  - the management page renders an `aas` toggle,
  - an admin can enable the `aas` subscription through the POST handler.
"""

import json


def _login_admin(client):
    client.post('/logoutUser', content_type='application/json')
    return client.post(
        '/loginUser',
        data=json.dumps({'username': 'User_Admin', 'password': '12345'}),
        content_type='application/json',
    )


class TestAasReachability:

    def test_known_apps_registry_includes_aas(self):
        """The shared app registry must list `aas`."""
        from app_registry import KNOWN_APPS
        assert 'aas' in KNOWN_APPS

    def test_subscription_page_renders_aas_toggle(self, app, client):
        """Admin must see an `aas` checkbox to enable the feature."""
        _login_admin(client)
        resp = client.get('/subscription-management')
        assert resp.status_code == 200
        assert b'id="aas"' in resp.data, \
            "subscription-management page has no 'aas' toggle — admin cannot enable AAS"

    def test_admin_can_enable_aas_subscription(self, app, client):
        """POSTing `aas` as subscribed must persist an enabled subscription row."""
        from models import Subscriptions, db
        _login_admin(client)
        resp = client.post(
            '/subscription-management',
            data=json.dumps({'subscribed': ['aas'], 'not_subscribed': []}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        with app.app_context():
            sub = Subscriptions.query.filter_by(apps='aas').first()
            assert sub is not None and sub.subscribed, \
                "aas subscription was not enabled by the management POST"
            # Clean up so the row doesn't leak into other tests.
            Subscriptions.query.filter_by(apps='aas').delete()
            db.session.commit()

    def test_role_management_renders_aas_permission_toggle(self, app, client):
        """Admin must see an `aas_export` checkbox to grant the AAS permission.

        Enabling the `aas` subscription is not enough to reach /aas-viewer — the
        route is also guarded by `@permission_required('aas_export')`.  The
        role-management page builds permission keys from checkbox ids, so it must
        render a checkbox whose id is exactly `aas_export`, gated by the `aas`
        subscription via `data-subscription`.
        """
        from models import Subscriptions, Permission, db
        from models import User
        with app.app_context():
            # the role-management page itself is guarded by subscription + permission
            sub = Subscriptions.query.filter_by(apps='role-management').first()
            previous = sub.subscribed if sub else None
            if not sub:
                sub = Subscriptions(apps='role-management')
                db.session.add(sub)
            sub.subscribed = True
            perm = Permission.query.filter_by(key='role-management').first() or Permission(key='role-management')
            role = User.query.filter_by(username='User_Admin').first().roles[0]
            added_perm = perm not in role.permissions
            if added_perm:
                role.permissions.append(perm)
            db.session.commit()
        try:
            _login_admin(client)
            resp = client.get('/role-management')
        finally:
            with app.app_context():
                sub = Subscriptions.query.filter_by(apps='role-management').first()
                if previous is None:
                    db.session.delete(sub)
                else:
                    sub.subscribed = previous
                if added_perm:
                    role = User.query.filter_by(username='User_Admin').first().roles[0]
                    role.permissions.remove(Permission.query.filter_by(key='role-management').first())
                db.session.commit()
        assert resp.status_code == 200
        assert b'This module is not activated.' not in resp.data
        assert b'id="aas_export"' in resp.data, \
            "role-management page has no 'aas_export' toggle — admin cannot grant the AAS permission"
        assert b'data-subscription="aas"' in resp.data, \
            "AAS permission toggle is not gated by the 'aas' subscription"

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

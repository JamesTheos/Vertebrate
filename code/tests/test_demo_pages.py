"""
test_demo_pages.py

Safety net for the branch merges (audit-dashboard, feature/aas-integration):
the pages and sidebars shown in the demo must keep working.

- An admin with every permission key opens every page with 200 and real content
  (not the "Module not activated" page).
- The sidebar shows each demo role exactly its menu entries; the branding stays.
- Pages outside a role's permissions stay closed (403).

Roles take their permission keys from seed_demo.py, so these tests follow the demo seed.
"""

import json
import re

import pytest
from werkzeug.security import generate_password_hash

from seed_demo import ALL_PERMISSION_KEYS, ROLES, SUBSCRIPTION_APPS

PASSWORD = 'smoke-pw'

# username -> (role name, permission keys); role names are prefixed so they never clash with other tests
DEMO_USERS = {
    'smoke.admin': ('smoke Admin-All', ALL_PERMISSION_KEYS),
    'smoke.pm': ('smoke Production Manager', ROLES['Production Manager']),
    'smoke.operator': ('smoke Operator', ROLES['Operator']),
}

# Every HTML page of the app (GET, no URL parameters)
PAGES = [
    '/', '/index', '/initial-index', '/data-tree',
    '/manufacturing-orders', '/order-management',
    '/workflow-overview', '/batch', '/process-instructions', '/sampling',
    '/equipment-overview', '/scada', '/3d-view',
    '/design-space-definition', '/design-space-representation',
    '/product_analytics', '/process-qbd-analysis',
    '/settings', '/plantconfig', '/processconfig', '/workflow-management',
    '/user-management', '/role-management', '/subscription-management',
    '/user-profile', '/updated-user', '/login-error', '/logout-message',
    '/audit/', '/aas-viewer',
]

# Sidebar links (besides Home) as the demo showed them per role
SIDEBAR_LINKS = {
    'smoke.admin': {
        '/data-tree', '/manufacturing-orders', '/order-management',
        '/workflow-overview', '/batch', '/process-instructions', '/sampling',
        '/equipment-overview', '/scada', '/3d-view',
        '/design-space-definition', '/design-space-representation',
        '/product_analytics', '/process-qbd-analysis',
        '/audit/', '/aas-viewer',
    },
    'smoke.pm':{'/data-tree', '/manufacturing-orders', '/order-management', '/workflow-overview'},
    'smoke.operator': {
        '/data-tree', '/workflow-overview', '/process-instructions', '/scada',
        '/design-space-representation',
    },
}

NOT_ACTIVATED = b'This module is not activated.'


@pytest.fixture(scope='module', autouse=True)
def demo_users(app):
    """Create the demo roles/users and subscribe every app; restore subscriptions afterwards."""
    from models import db, User, Role, Permission, Subscriptions

    with app.app_context():
        previous = {s.apps: s.subscribed for s in Subscriptions.query.all()}
        for key in SUBSCRIPTION_APPS:
            sub = Subscriptions.query.filter_by(apps=key).first()
            if sub:
                sub.subscribed = True
            else:
                db.session.add(Subscriptions(apps=key, subscribed=True))

        for username, (role_name, keys) in DEMO_USERS.items():
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                role = Role(name=role_name)
                db.session.add(role)
            for key in keys:
                perm = Permission.query.filter_by(key=key).first()
                if not perm:
                    perm = Permission(key=key)
                    db.session.add(perm)
                if perm not in role.permissions:
                    role.permissions.append(perm)
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(username=username, password=generate_password_hash(PASSWORD))
                db.session.add(user)
            if role not in user.roles:
                user.roles.append(role)
        db.session.commit()

    yield

    with app.app_context():
        for sub in Subscriptions.query.all():
            if sub.apps in previous:
                sub.subscribed = previous[sub.apps]
            else:
                db.session.delete(sub)
        db.session.commit()


def login(app, username):
    client = app.test_client()
    resp = client.post('/loginUser', data=json.dumps({'username': username, 'password': PASSWORD}),
                       content_type='application/json')
    assert resp.get_json() == {'redirect': '/index'}, f"login as {username} failed"
    return client


def sidebar_links(html):
    nav = re.search(r'<nav class\s*=\s*"sidebar">(.*?)</nav>', html, re.S)
    assert nav, "sidebar <nav> not found"
    return set(re.findall(r'href="([^"]+)"', nav.group(1))) - {'/index'}


@pytest.mark.parametrize('path', PAGES)
def test_admin_opens_every_page(app, path):
    resp = login(app, 'smoke.admin').get(path)
    assert resp.status_code == 200, f"{path} returned {resp.status_code}"
    assert resp.content_type.startswith('text/html')
    assert NOT_ACTIVATED not in resp.data, f"{path} shows 'Module not activated'"


@pytest.mark.parametrize('username', sorted(SIDEBAR_LINKS))
def test_sidebar_shows_exactly_the_role_entries(app, username):
    html = login(app, username).get('/index').get_data(as_text=True)
    assert sidebar_links(html) == SIDEBAR_LINKS[username]


def test_branding_on_every_page(app):
    html = login(app, 'smoke.admin').get('/index').get_data(as_text=True)
    assert '<title>Data Vertebrate · ' in html
    assert 'Theos-CES' in html and 'Data Vertebrate' in html
    assert 'images/favicon.svg' in html


@pytest.mark.parametrize('username, path', [
    ('smoke.operator', '/manufacturing-orders'),
    ('smoke.operator', '/order-management'),
    ('smoke.operator', '/role-management'),
    ('smoke.pm', '/process-instructions'),
    ('smoke.pm', '/design-space-definition'),
    ('smoke.pm', '/user-management'),
    ('smoke.operator', '/audit/'),
    ('smoke.pm', '/audit/'),
    ('smoke.operator', '/aas-viewer'),
    ('smoke.pm', '/aas-viewer'),
])
def test_role_cannot_open_pages_outside_its_permissions(app, username, path):
    assert login(app, username).get(path).status_code == 403

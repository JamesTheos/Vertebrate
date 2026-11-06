"""
test_seed_demo.py

create_app() seeds User_Admin with the default password on an empty database
(audit-dashboard).  A full demo seed must still apply DEMO_ADMIN_PW over that
default, but never overwrite a password someone has changed since, and it must
give User_Admin the Admin-All role.
"""

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

import seed_demo

DEMO_ADMIN_PW = 'demo-admin-pw'


@pytest.fixture()
def user_admin(app, monkeypatch):
    """User_Admin with a given password; password and roles are restored afterwards."""
    from models import db, User

    monkeypatch.setattr(seed_demo, 'STARTUP', False)
    monkeypatch.setattr(seed_demo, 'changes', [])
    monkeypatch.setattr(seed_demo, 'USERS', [('User_Admin', DEMO_ADMIN_PW, ['Admin-All'], False)])

    with app.app_context():
        user = User.query.filter_by(username='User_Admin').first()
        if user is None:
            user = User(username='User_Admin', password=generate_password_hash('12345'))
            db.session.add(user)
            db.session.commit()
        original = (user.password, list(user.roles))

    def set_password(password):
        with app.app_context():
            User.query.filter_by(username='User_Admin').first().password = generate_password_hash(password)
            db.session.commit()

    yield set_password

    with app.app_context():
        user = User.query.filter_by(username='User_Admin').first()
        user.password = original[0]
        user.roles = [db.session.merge(role) for role in original[1]]
        db.session.commit()


def run_seed(app):
    from models import db
    with app.app_context():
        seed_demo.seed_roles()
        seed_demo.seed_users()
        db.session.commit()


def admin(app):
    from models import User
    with app.app_context():
        user = User.query.filter_by(username='User_Admin').first()
        return user.password, [role.name for role in user.roles]


def test_seed_sets_demo_admin_password_over_the_app_default(app, user_admin):
    user_admin('12345')
    run_seed(app)
    password, roles = admin(app)
    assert check_password_hash(password, DEMO_ADMIN_PW)
    assert 'Admin-All' in roles


def test_seed_keeps_a_changed_admin_password(app, user_admin):
    user_admin('changed-by-admin')
    run_seed(app)
    password, roles = admin(app)
    assert check_password_hash(password, 'changed-by-admin')
    assert 'Admin-All' in roles

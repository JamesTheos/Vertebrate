import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import User, Role, Permission, Subscriptions, RolePermission


def test_user_role_permission_crud(db):
    ts = int(time.time())
    role_name = f'test_creator_{ts}'
    perm_key = f'test-perm-{ts}'
    username = f'test_alice_{ts}'

    # Create role and permission
    role = Role(name=role_name)
    perm = Permission(key=perm_key)
    db.session.add_all([role, perm])
    db.session.commit()

    role.permissions.append(perm)
    db.session.commit()

    r = Role.query.filter_by(name=role_name).first()
    assert r is not None
    assert any(p.key == perm_key for p in r.permissions)

    user = User(username=username, password='hash')
    user.roles.append(role)
    db.session.add(user)
    db.session.commit()

    u = User.query.filter_by(username=username).first()
    assert u is not None
    assert isinstance(u.id, int)
    assert any(ro.name == role_name for ro in u.roles)

    # Cleanup
    u.roles.clear()
    db.session.commit()
    db.session.delete(u)
    RolePermission.query.filter_by(role_id=r.id).delete()
    db.session.delete(perm)
    db.session.delete(r)
    db.session.commit()


def test_subscriptions_default_false(db):
    ts = int(time.time())
    app_name = f'test-app-{ts}'

    s = Subscriptions(apps=app_name)
    db.session.add(s)
    db.session.commit()

    got = db.session.get(Subscriptions, app_name)
    assert got is not None
    assert got.subscribed is False

    # Cleanup
    db.session.delete(got)
    db.session.commit()

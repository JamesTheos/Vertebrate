from code.models import User, Role, Permission, Subscriptions, db


def test_user_role_permission_crud(db):
    # Create role and permission
    role = Role(name='creator')
    perm = Permission(key='user-management')
    db.session.add_all([role, perm])
    db.session.commit()

    # Assign permission to role using relationship
    role.permissions.append(perm)
    db.session.commit()

    # Verify association
    r = Role.query.filter_by(name='creator').first()
    assert r is not None
    assert any(p.key == 'user-management' for p in r.permissions)

    # Create user with role
    user = User(username='alice', password='hash')
    user.roles.append(role)
    db.session.add(user)
    db.session.commit()

    u = User.query.filter_by(username='alice').first()
    assert u is not None
    # property id returns uid
    assert isinstance(u.id, int)
    assert any(ro.name == 'creator' for ro in u.roles)


def test_subscriptions_default_false(db):
    # By default subscribed should be False
    s = Subscriptions(apps='order-management')
    db.session.add(s)
    db.session.commit()

    got = Subscriptions.query.get('order-management')
    assert got is not None
    assert got.subscribed is False

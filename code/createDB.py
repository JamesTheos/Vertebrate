from app import db, create_app
from models import Subscriptions, User, MetaInfo, Role, RolePermission, Permission, UserRoles
import os
import json
from werkzeug.security import generate_password_hash
from sqlalchemy import text

# ============================================================================
# CONFIG
# ============================================================================

config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

cluster_id = config.get("clusterid")
admin_password_hash = generate_password_hash('12345')

# ============================================================================
# HELPERS
# ============================================================================

def _is_postgres(engine):
    return engine.dialect.name == 'postgresql'


def _setup_audit_schema(engine):
    """Create audit_trail schema and AuditLog table (PostgreSQL only)."""
    db.session.execute(text('CREATE SCHEMA IF NOT EXISTS audit_trail'))
    db.session.commit()
    db.create_all()
    print("Audit trail schema and tables created")


def _install_immutability_trigger():
    """
    Install PL/pgSQL trigger that prevents UPDATE/DELETE on audit_logs.
    21 CFR Part 11 §11.10(e) — audit records must be immutable.
    """
    db.session.execute(text('''
        CREATE OR REPLACE FUNCTION audit_trail.prevent_audit_modification()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                '21 CFR Part 11: audit log records are immutable and cannot be modified or deleted';
            RETURN NULL;  -- required by PL/pgSQL even though unreachable after RAISE
        END;
        $$;
    '''))

    db.session.execute(text('''
        DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON audit_trail.audit_logs;
    '''))

    db.session.execute(text('''
        CREATE TRIGGER trg_audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_trail.audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_trail.prevent_audit_modification();
    '''))

    db.session.commit()
    print("21 CFR Part 11: audit_logs immutability trigger installed")


def _seed_creator_role():
    """Create 'creator' role with role-management and user-management permissions."""
    creator_role = Role.query.filter_by(name='creator').first()
    if not creator_role:
        creator_role = Role(name='creator')
        db.session.add(creator_role)
        db.session.flush()
        print("Rolle 'creator' wurde erstellt.")

    for perm_key in ['role-management', 'user-management']:
        perm = Permission.query.filter_by(key=perm_key).first()
        if not perm:
            perm = Permission(key=perm_key)
            db.session.add(perm)
            db.session.flush()
        if not RolePermission.query.filter_by(permission_id=perm.id, role_id=creator_role.id).first():
            db.session.add(RolePermission(permission_id=perm.id, role_id=creator_role.id))

    db.session.flush()
    print("Permissions für 'creator' wurden hinzugefügt.")
    return creator_role


def _seed_admin_user(creator_role):
    """Create User_Admin with creator role if not already present."""
    admin_user = User.query.filter_by(username='User_Admin').first()
    if not admin_user:
        admin_user = User(
            username='User_Admin',
            password=admin_password_hash,
            roles=[creator_role]
        )
        db.session.add(admin_user)
        db.session.flush()
        print("Admin User 'User_Admin' wurde erstellt.")

    if not UserRoles.query.filter_by(user_id=admin_user.id, role_id=creator_role.id).first():
        db.session.add(UserRoles(user_id=admin_user.id, role_id=creator_role.id))
        db.session.flush()


def _seed_subscriptions():
    """Seed all core apps as unsubscribed by default."""
    from app_registry import KNOWN_APPS

    for app_name in KNOWN_APPS:
        sub = Subscriptions.query.filter_by(apps=app_name).first()
        if not sub:
            db.session.add(Subscriptions(apps=app_name, subscribed=False))
        else:
            sub.subscribed = False

    print("All apps seeded as unsubscribed (False) by default.")


# ============================================================================
# MAIN
# ============================================================================

app = create_app()

with app.app_context():
    db.create_all()

    if _is_postgres(db.engine):
        _setup_audit_schema(db.engine)
        _install_immutability_trigger()
    else:
        print(f"Dialect: {db.engine.dialect.name} — audit schema and immutability trigger skipped (PostgreSQL only)")

    # Cluster ID
    if not MetaInfo.query.filter_by(id=cluster_id).first():
        db.session.add(MetaInfo(id=cluster_id))
        print("Cluster ID wurde in MetaInfo hinzugefügt.")

    creator_role = _seed_creator_role()
    _seed_admin_user(creator_role)
    _seed_subscriptions()

    db.session.commit()
    print("Database initialisation complete.")
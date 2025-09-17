from app import db, create_app
from models import Subscriptions, User, MetaInfo, Role, RolePermission, Permission, UserRoles
import os
import json
from werkzeug.security import generate_password_hash


# Config laden
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

cluster_id = config.get("clusterid")

# Default Passwort für Admin
admin_password_hash = generate_password_hash('12345')

app = create_app()

with app.app_context():
    # Tabellen anlegen
    db.create_all()

    # Cluster ID in MetaInfo speichern, falls nicht vorhanden
    if not MetaInfo.query.filter_by(id=cluster_id).first():
        db.session.add(MetaInfo(id=cluster_id))
        print("Cluster ID wurde in MetaInfo hinzugefügt.")

    # Rollen anlegen, falls noch nicht vorhanden
    creator_role = Role.query.filter_by(name='creator').first()
    if not creator_role:
        creator_role = Role(name='creator')
        db.session.add(creator_role)
        db.session.flush()  # ensures creator_role.id is available
        print("Rolle 'creator' wurde erstellt.")

    # Beispiel-Permissions zur Rolle hinzufügen
    permissions = ['role-management', 'user-management']
    for perm in permissions:
        perms = Permission.query.filter_by(key=perm).first()
        if not perms:
            perms = Permission(key=perm)
            db.session.add(perms)
            db.session.flush()
        rp = RolePermission.query.filter_by(permission_id=perms.id, role_id=creator_role.id).first()
        if not rp:
            rp = RolePermission(permission_id=perms.id, role_id=creator_role.id)
            db.session.add(rp)
    db.session.flush()
    print("Permissions für 'creator' wurden hinzugefügt.")

    # Admin-User prüfen/erstellen
    admin_user = User.query.filter_by(username='User_Admin').first()
    if not admin_user:
        admin_user = User(
            username='User_Admin',
            password=admin_password_hash,
            roles=[creator_role]  # assign ORM role object
        )
        db.session.add(admin_user)
        db.session.flush()

        # Assign 'creator' role to admin user (if UserRoles is separate mapping)
        admin_user_role = UserRoles.query.filter_by(user_id=admin_user.id, role_id=creator_role.id).first()
        if not admin_user_role:
            admin_user_role = UserRoles(user_id=admin_user.id, role_id=creator_role.id)
            db.session.add(admin_user_role)
            db.session.flush()
        print("Admin User 'User_Admin' wurde erstellt.")

    # create user-role mapping using real role id (just to be safe)
    if not UserRoles.query.filter_by(user_id=admin_user.id, role_id=creator_role.id).first():
        db.session.add(UserRoles(user_id=admin_user.id, role_id=creator_role.id))

    
    # Seed all core apps as unsubscribed by default
    core_apps = [
        "manufacturing-orders",
        "order-management",
        "workflow-overview",
        "batch",
        "process-instructions",
        "sampling",
        "equipment",
        "pid",
        "3d-view",
        "design-space-definition",
        "design-space-representation",
        "product-analytics",
        "process-qbd-analytics",
        "plant-configuration",
        "process-configuration",
        "workflow-management",
        "user-management",
        "role-management"
    ]

    for app_name in core_apps:
        sub = Subscriptions.query.filter_by(apps=app_name).first()
        if not sub:
            sub = Subscriptions(apps=app_name, subscribed=False)
            db.session.add(sub)
        else:
            sub.subscribed = False

    db.session.commit()
    print("All apps seeded as unsubscribed (False) by default.")


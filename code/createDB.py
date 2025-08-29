from app import db, create_app
from models import User, MetaInfo, Role, RolePermission, Permission, UserRoles
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
    id_entry = MetaInfo.query.filter_by(id=cluster_id).first()
    if not id_entry:
        cluster_id_entry = MetaInfo(id=cluster_id)
        db.session.add(cluster_id_entry)
        db.session.commit()
        print("Cluster ID wurde in MetaInfo hinzugefügt.")

    # Rollen anlegen, falls noch nicht vorhanden
    admin_role = Role.query.filter_by(name='creator').first()
    if not admin_role:
        admin_role = Role(name='creator')
        db.session.add(admin_role)
        db.session.commit()
        print("Rolle 'creator' wurde erstellt.")

        # Beispiel-Permissions zur Rolle hinzufügen
        permissions = ['role-management', 'user-management']
        for perm in permissions:
            perms = Permission.query.filter_by(key=perm).first()
            if not perms:
                perms = Permission(key=perm)
                db.session.add(perms)
                db.session.commit()
            rp = RolePermission.query.filter_by(permission_id=perms.id, role_id=hash('creator')).first()
            if not rp:
                rp = RolePermission(permission_id=perms.id, role_id=hash('creator'))
                db.session.add(rp)
        db.session.commit()
        print("Permissions für 'creator' wurden hinzugefügt.")
    admin_user = User.query.filter_by(username='User_Admin').first()
    if not admin_user:
        admin_user = User(
            username='User_Admin',
            password=admin_password_hash,
            roles=[admin_role]
        )
        db.session.add(admin_user)
        db.session.commit()
        # Assign 'creator' role to admin user
        admin_user_role = UserRoles.query.filter_by(user_id=admin_user.id, role_id=hash('creator')).first()
        if not admin_user_role:
            admin_user_role = UserRoles(user_id=admin_user.id, role_id=hash('creator'))
            db.session.add(admin_user_role)
            db.session.commit()
        print("Admin User 'User_Admin' wurde erstellt.")

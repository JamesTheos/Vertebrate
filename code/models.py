from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()
audit_db = SQLAlchemy()

# Define metainfo
class MetaInfo(db.Model):
    __tablename__ = 'metainfo'
    id = db.Column(db.String, primary_key=True)


# Define Audit Model

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    __table_args__ = {'schema': 'audit_trail'}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False,
                          default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(255), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)
    record_type = db.Column(db.String(100), nullable=False)
    record_id = db.Column(db.String(100), nullable=True)
    field_name = db.Column(db.String(255), nullable=True)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    change_reason = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    session_id = db.Column(db.String(255), nullable=True)
    request_method = db.Column(db.String(10), nullable=True)
    endpoint = db.Column(db.String(255), nullable=True)
    checksum = db.Column(db.String(64), nullable=True)


#Define user class

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    uid = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, nullable=False, unique = True)
    password = db.Column(db.String, nullable=False)
    roles = db.relationship('Role', secondary='user_roles', back_populates='users')

    @property
    def id(self):
        return self.uid
    
#Define Mapping table

class UserRoles(db.Model):
    __tablename__ = 'user_roles'
    user_id = db.Column(db.Integer, db.ForeignKey('users.uid'), primary_key=True)
    role_id = db.Column(db.String, db.ForeignKey('roles.id'), primary_key=True)


#Define role class

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    users = db.relationship('User', secondary='user_roles', back_populates='roles')
    permissions = db.relationship('Permission', secondary='role_permissions', back_populates='roles')

# Define permission class

class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String, unique=True, nullable=False)
    roles = db.relationship('Role', secondary='role_permissions', back_populates='permissions')


# Define role permission class

class RolePermission(db.Model):
    __tablename__ = 'role_permissions'
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), primary_key=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id'), primary_key=True)


# Define subscriptions class
class Subscriptions(db.Model):
    __tablename__ = "app_subscriptions"
    apps = db.Column(db.String, primary_key=True)
    subscribed = db.Column(db.Boolean, nullable=False, default=False)


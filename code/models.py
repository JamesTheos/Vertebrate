from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

#Main operational database
db = SQLAlchemy()

#audit DB
audit_db = SQLAlchemy()

# Define metainfo

class MetaInfo(db.Model):
    __tablename__ = 'metainfo'
    id = db.Column(db.String, primary_key=True)

#Define Audit Logs in AuditDB

class AuditLog(audit_db.Model):
    __tablename__ = 'audit_logs'
    __bind_key__ = 'audit' 
    
    # Primary identification
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Timestamp (server-generated, immutable)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # WHO - User identification
    user_id = db.Column(db.Integer, db.ForeignKey('users.uid'), nullable=False)
    username = db.Column(db.String, nullable=False)  # Denormalized for immutability
    
    # WHAT - Action details
    action_type = db.Column(db.String, nullable=False)  # CREATE, UPDATE, DELETE, LOGIN, LOGOUT
    record_type = db.Column(db.String, nullable=False)  # USER, ROLE, PROCESS_PARAMETER, PLC_CONFIG, etc.
    record_id = db.Column(db.String, nullable=True)     # ID of affected record
    
    # Change tracking
    field_name = db.Column(db.String, nullable=True)    # Specific field changed
    old_value = db.Column(db.Text, nullable=True)       # Previous value
    new_value = db.Column(db.Text, nullable=True)       # New value
    
    # WHY - Reason for change (21 CFR Part 11 requirement)
    change_reason = db.Column(db.Text, nullable=True)
    
    # Additional context
    ip_address = db.Column(db.String, nullable=True)
    session_id = db.Column(db.String, nullable=True)
    request_method = db.Column(db.String, nullable=True)  # POST, PUT, DELETE
    endpoint = db.Column(db.String, nullable=True)        # Flask route
    
    # Integrity protection
    checksum = db.Column(db.String, nullable=True)  # SHA-256 hash of record
    
    # Prevent modifications
    def __setattr__(self, name, value):
        if hasattr(self, 'id') and self.id is not None:
            raise AttributeError("Audit logs are immutable")
        super().__setattr__(name, value)



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


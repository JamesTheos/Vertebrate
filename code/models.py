from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()
# Define metainfo
class MetaInfo(db.Model):
    __tablename__ = 'metainfo'
    id = db.Column(db.String, primary_key=True)

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


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
    role = db.Column(db.String)
    @property
    def id(self):
        return self.uid

 
    
    
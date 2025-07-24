from app import db, create_app
from models import User,MetaInfo
import os
import json
from werkzeug.security import generate_password_hash

config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

cluster_id = config.get("clusterid")

kennwort = generate_password_hash('12345')  # Default password for the admin user

app = create_app()
with app.app_context():
    db.create_all()
    #Save current cluster_id in metainfo table
    id_entry = MetaInfo.query.filter_by(id=cluster_id).first()
    if not id_entry:
        cluster_id_entry = MetaInfo(id=cluster_id)
        db.session.add(cluster_id_entry)
        db.session.commit()
        print("Database created and cluster_id has been added")
    # Create an admin user if it doesn't exist
    admin_user = User.query.filter_by(username='User_Admin').first()
    if not admin_user:
        admin_user = User(username='User_Admin', password=kennwort, role='creator')
        db.session.add(admin_user)
        db.session.commit()
        print("Database created and User_Admin has been added")
from app import db, create_app
from models import User

app = create_app()
with app.app_context():
    db.create_all()
    # Create an admin user if it doesn't exist
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(username='admin', password='admin', role='admin')
        db.session.add(admin_user)
        db.session.commit()
        print("Database created and admin user added")
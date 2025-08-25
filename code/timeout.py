from flask import session, redirect, url_for
from flask_login import current_user, logout_user
from datetime import datetime, UTC

INACTIVITY_TIMEOUT = 300  # seconds

def register_timeout_hook(app):
    @app.before_request
    def check_inactivity():
        if current_user.is_authenticated:
            #print("A login user is authenticated, checking inactivity timeout.")
            now = datetime.now(UTC)
            last_activity = session.get('last_activity')

            if last_activity:
                last_active = datetime.fromisoformat(last_activity)
                elapsed = (now - last_active).total_seconds()
                if elapsed > INACTIVITY_TIMEOUT:
                    #print("Logging out due to inactivity.")
                    logout_user()
                    session.pop('last_activity', None)
                    return redirect(url_for('Logout_message'))

            session['last_activity'] = now.isoformat()
        return None

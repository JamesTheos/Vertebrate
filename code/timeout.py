import os
from flask import session, redirect, url_for
from flask_login import current_user, logout_user
from datetime import datetime, UTC


def session_idle_minutes():
    """Idle logout in minutes: env SESSION_IDLE_MINUTES (the demo sets 60), default 5."""
    try:
        return max(1.0, float(os.environ.get('SESSION_IDLE_MINUTES', '5')))
    except ValueError:
        return 5.0


INACTIVITY_TIMEOUT = int(session_idle_minutes() * 60)  # seconds


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

from functools import wraps
from flask import render_template, Blueprint, request
from models import Subscriptions, db

subscriptions = Blueprint("subscriptions", __name__)

@subscriptions.route("/subscription-management", methods=["POST"])
def subscription_management():
    data = request.get_json()  # Get JSON data
    subscribed_list = data.get("subscribed", [])
    not_subscribed_list = data.get("not_subscribed", [])

    # Update DB — upsert each app to its requested state
    for app_name, flag in ([(a, True) for a in subscribed_list]
                           + [(a, False) for a in not_subscribed_list]):
        sub = (Subscriptions.query.filter_by(apps=app_name).first()
               or Subscriptions(apps=app_name))
        sub.subscribed = flag
        db.session.add(sub)

    db.session.commit()
    return {"status": "success"}  # JSON response


def check_subscription(arg=None):
    """Decorator that checks subscription status in the DB.

    Supports two call styles:
        @check_subscription                  # bare — app_name derived from view function name
        @check_subscription('my_app_name')   # explicit app_name string
    """
    # When used bare, `arg` is the view function; when explicit, it's the name.
    explicit_name = None if callable(arg) else arg

    def decorator(func):
        name = explicit_name if explicit_name is not None else func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            db.session.expire_all()
            sub = Subscriptions.query.filter_by(apps=name).with_for_update().first()
            if sub and bool(sub.subscribed):
                return func(*args, **kwargs)
            return render_template("subscription-denied.html")

        return wrapper

    return decorator(arg) if callable(arg) else decorator

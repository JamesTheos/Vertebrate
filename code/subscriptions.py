from functools import wraps
from flask import render_template, Blueprint, request
from models import Subscriptions, db

subscriptions = Blueprint("subscriptions", __name__)

@subscriptions.route("/subscription-management", methods=["POST"])
def subscription_management():
    data = request.get_json()  # Get JSON data
    subscribed_list = data.get("subscribed", [])
    not_subscribed_list = data.get("not_subscribed", [])

    # Update DB
    for app_name in subscribed_list:
        sub = Subscriptions.query.filter_by(apps=app_name).first()
        if not sub:
            sub = Subscriptions(apps=app_name, subscribed=True)
            db.session.add(sub)
        else:
            sub.subscribed = True

    for app_name in not_subscribed_list:
        sub = Subscriptions.query.filter_by(apps=app_name).first()
        if not sub:
            sub = Subscriptions(apps=app_name, subscribed=False)
            db.session.add(sub)
        else:
            sub.subscribed = False

    db.session.commit()
    return {"status": "success"}  # JSON response


def check_subscription(func_or_app_name=None):
    """Decorator that checks subscription status in the DB.

    Supports two call styles:
        @check_subscription                  # bare — app_name derived from view function name
        @check_subscription('my_app_name')   # explicit app_name string
    """
    # --- bare usage: @check_subscription (no parentheses, func passed directly) ---
    if callable(func_or_app_name):
        func = func_or_app_name
        app_name = func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            db.session.expire_all()
            sub = Subscriptions.query.filter_by(apps=app_name).with_for_update().first()
            if sub and bool(sub.subscribed):
                return func(*args, **kwargs)
            else:
                return render_template("subscription-denied.html")

        return wrapper

    # --- called with explicit app_name: @check_subscription('name') ---
    def decorator(func):
        name = func_or_app_name if func_or_app_name is not None else func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            db.session.expire_all()
            sub = Subscriptions.query.filter_by(apps=name).with_for_update().first()
            if sub and bool(sub.subscribed):
                return func(*args, **kwargs)
            else:
                return render_template("subscription-denied.html")

        return wrapper
    return decorator

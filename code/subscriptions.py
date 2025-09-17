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


def check_subscription(app_name):
    """Decorator that checks subscription status in the DB."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            db.session.expire_all()  # Ensure fresh data from DB
            sub = Subscriptions.query.filter_by(apps=app_name).with_for_update().first()
            #print(f"app_name: {app_name}")
            #print(f"sub: {sub}, subscribed={sub.subscribed if sub else None}")

            if sub and bool(sub.subscribed):   # explicit True check
                return func(*args, **kwargs)
            else:
                return render_template("subscription-denied.html")

        return wrapper
    return decorator

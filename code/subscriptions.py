from functools import wraps
from flask import render_template

# Lists to hold app names
subscribed_list = []
not_subscribed_list = []

def subscribed(name):
    # Add to list immediately when decorator is applied
    subscribed_list.append(name)
    print(f"📌 Registered subscribed: {name}")

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

def not_subscribed(name):
    not_subscribed_list.append(name)
    print(f"📌 Registered not subscribed: {name}")

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return render_template('subscription-denied.html')
        return wrapper
    return decorator

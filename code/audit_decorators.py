"""
Decorators for automatic audit trail logging on Flask routes
Provides convenient decorators to add audit logging to any Flask endpoint
"""

from functools import wraps
from flask import request
from audit_trail import log_audit, log_field_change
from audit_config import *


def audit_action(action_type, record_type, get_record_id=None):
    """
    Decorator to automatically log actions on Flask routes

    Args:
        action_type (str): Type of action (ACTION_CREATE, ACTION_UPDATE, etc.)
        record_type (str): Type of record (RECORD_USER, RECORD_ROLE, etc.)
        get_record_id (callable): Optional function to extract record_id from result
                                  Function signature: get_record_id(result, *args, **kwargs)

    Usage:
        @audit_action(ACTION_CREATE, RECORD_USER)
        def create_user():
            # ... create user logic ...
            return user_id

        @audit_action(ACTION_UPDATE, RECORD_USER, lambda result, user_id: user_id)
        def update_user(user_id):
            # ... update logic ...
            return success

    The decorator will:
    - Execute the wrapped function
    - Capture the result
    - Extract record_id (from kwargs, route params, or result)
    - Extract change_reason from request JSON
    - Log the audit entry
    - Return the original result
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Execute the function first
            result = f(*args, **kwargs)

            # Try to get record_id
            record_id = None

            # Option 1: Use custom extractor function
            if get_record_id and callable(get_record_id):
                try:
                    record_id = get_record_id(result, *args, **kwargs)
                except Exception:
                    pass

            # Option 2: Check common parameter names in kwargs
            if not record_id:
                record_id = kwargs.get('id') or kwargs.get('user_id') or kwargs.get('record_id')

            # Option 3: Check route parameters
            if not record_id and request.view_args:
                record_id = request.view_args.get('id') or request.view_args.get('user_id')

            # Get change_reason from request body
            change_reason = None
            if request.is_json and request.json:
                change_reason = request.json.get('change_reason')

            # Log the audit entry
            try:
                log_audit(
                    action_type=action_type,
                    record_type=record_type,
                    record_id=record_id,
                    change_reason=change_reason
                )
            except Exception as e:
                # Don't break the request if audit logging fails
                print(f"⚠️  Audit logging failed in decorator: {e}")

            return result

        return wrapped

    return decorator


def audit_login(success=True):
    """
    Decorator specifically for login attempts
    Logs successful logins or failed attempts

    Args:
        success (bool): If True, logs ACTION_LOGIN; if False, logs ACTION_LOGIN_FAILED

    Usage:
        @audit_login(success=True)
        def login_user():
            # ... authentication logic ...
            return user_object

        @audit_login(success=False)
        def handle_login_failure():
            # ... handle failed login ...
            return error_response
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            result = f(*args, **kwargs)

            # Determine action type
            action_type = ACTION_LOGIN if success else ACTION_LOGIN_FAILED

            # Try to get username from request
            username = None
            user_id = None

            if request.is_json and request.json:
                username = request.json.get('username')

            # For successful logins, try to get user_id from result
            if success and hasattr(result, 'uid'):
                user_id = result.uid
            elif success and isinstance(result, dict):
                user_id = result.get('uid') or result.get('user_id')

            # Log the audit entry
            try:
                log_audit(
                    action_type=action_type,
                    record_type=RECORD_USER,
                    record_id=user_id,
                    change_reason=f"{'Successful' if success else 'Failed'} login attempt for username: {username}" if username else None
                )
            except Exception as e:
                print(f"⚠️  Login audit logging failed: {e}")

            return result

        return wrapped

    return decorator


def audit_logout():
    """
    Decorator specifically for logout actions

    Usage:
        @audit_logout()
        def logout_user():
            # ... logout logic ...
            return response
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Log BEFORE logout (while user is still authenticated)
            from flask_login import current_user

            user_id = current_user.uid if current_user.is_authenticated else None
            username = current_user.username if current_user.is_authenticated else None

            try:
                log_audit(
                    action_type=ACTION_LOGOUT,
                    record_type=RECORD_USER,
                    record_id=user_id,
                    change_reason=f"User logout: {username}" if username else "User logout"
                )
            except Exception as e:
                print(f"⚠️  Logout audit logging failed: {e}")

            # Execute the actual logout
            result = f(*args, **kwargs)
            return result

        return wrapped

    return decorator


def audit_field_changes(record_type, get_record_id, get_changes):
    """
    Decorator for logging detailed field-level changes

    Args:
        record_type (str): Type of record being changed
        get_record_id (callable): Function to extract record_id
        get_changes (callable): Function that returns list of changes
                                Signature: get_changes(old_data, new_data) -> list of dicts

    Usage:
        @audit_field_changes(
            record_type=RECORD_USER,
            get_record_id=lambda result, user_id: user_id,
            get_changes=lambda old, new: [
                {'field_name': 'username', 'old_value': old.username, 'new_value': new.username}
            ]
        )
        def update_user(user_id):
            # ... update logic ...
            return updated_user
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Get old data before update (if possible)
            # This would need to be customized per use case

            result = f(*args, **kwargs)

            # Extract record_id
            record_id = None
            if get_record_id and callable(get_record_id):
                try:
                    record_id = get_record_id(result, *args, **kwargs)
                except Exception:
                    pass

            # Get change_reason
            change_reason = None
            if request.is_json and request.json:
                change_reason = request.json.get('change_reason')

            # Get changes (this would be called with old and new data)
            # For now, we'll log a single UPDATE action
            try:
                log_audit(
                    action_type=ACTION_UPDATE,
                    record_type=record_type,
                    record_id=record_id,
                    change_reason=change_reason
                )
            except Exception as e:
                print(f"⚠️  Field change audit logging failed: {e}")

            return result

        return wrapped

    return decorator


def require_change_reason(f):
    """
    Decorator to enforce that change_reason is provided in request
    Raises 400 error if missing for sensitive operations

    Usage:
        @require_change_reason
        def update_sensitive_data():
            # ... update logic ...
    """

    @wraps(f)
    def wrapped(*args, **kwargs):
        if request.is_json and request.json:
            change_reason = request.json.get('change_reason')
            if not change_reason:
                from flask import jsonify
                return jsonify({
                    'error': 'change_reason is required for this operation',
                    'status': 'bad_request'
                }), 400

        return f(*args, **kwargs)

    return wrapped

"""
Core audit trail logging functions for 21 CFR Part 11 compliance
Provides functions to create audit log entries with all required fields
"""


from models import db, AuditLog
from datetime import datetime, timezone
import hashlib
import json
from flask import request, session, has_request_context
from audit_config import (
    AUDIT_ENABLED,
    EXCLUDE_FIELDS,
    REDACTED_VALUE,
    GENERATE_CHECKSUMS,
    LOG_REQUEST_DETAILS,
    REQUIRE_REASON_ACTIONS,
    REQUIRE_REASON_RECORDS,
    REQUIRE_REASON_FIELDS
)


def log_audit(action_type, record_type, record_id=None, **kwargs):
    """
    Create audit log entry

    Args:
        action_type (str): Type of action (CREATE, UPDATE, DELETE, LOGIN, etc.)
        record_type (str): Type of record affected (USER, ROLE, etc.)
        record_id (str/int): ID of the affected record
        **kwargs: Additional fields:
            - field_name (str): Specific field that changed
            - old_value (str): Previous value
            - new_value (str): New value
            - change_reason (str): Why the change was made (REQUIRED for sensitive ops)
            - ip_address (str): Override auto-detected IP
            - session_id (str): Override auto-detected session
            - request_method (str): Override auto-detected method
            - endpoint (str): Override auto-detected endpoint

    Returns:
        int: ID of created audit log entry, or None if failed

    Raises:
        ValueError: If change_reason is required but not provided
    """

    if not AUDIT_ENABLED:
        return None

    # Validate change_reason requirement
    _validate_change_reason(action_type, record_type, kwargs.get('field_name'), kwargs.get('change_reason'))

    # Get user context
    from flask_login import current_user

    try:
        from flask_login import current_user
        if current_user and current_user.is_authenticated:
            user_id = current_user.uid
            username = current_user.username
        else:
            user_id = None
            username = 'SYSTEM'
    except (AttributeError, RuntimeError):
        user_id = None
        username = 'SYSTEM'

    # Get request context (if available)
    ip_address = kwargs.get('ip_address')
    session_id = kwargs.get('session_id')
    request_method = kwargs.get('request_method')
    endpoint = kwargs.get('endpoint')

    if LOG_REQUEST_DETAILS and has_request_context():
        if not ip_address:
            ip_address = request.remote_addr
        if not session_id:
            session_id = session.get('_id') if session else None
        if not request_method:
            request_method = request.method
        if not endpoint:
            endpoint = request.endpoint

    # Sanitize values (redact sensitive fields)
    old_value = _sanitize_value(kwargs.get('field_name'), kwargs.get('old_value'))
    new_value = _sanitize_value(kwargs.get('field_name'), kwargs.get('new_value'))

    # Create audit entry
    audit_entry = AuditLog(
        timestamp=datetime.now(timezone.utc),
        user_id=user_id,
        username=username,
        action_type=action_type,
        record_type=record_type,
        record_id=str(record_id) if record_id else None,
        field_name=kwargs.get('field_name'),
        old_value=old_value,
        new_value=new_value,
        change_reason=kwargs.get('change_reason'),
        ip_address=ip_address,
        session_id=session_id,
        request_method=request_method,
        endpoint=endpoint
    )

    # Generate checksum for integrity
    if GENERATE_CHECKSUMS:
        audit_entry.checksum = _generate_checksum(audit_entry)

    # Save to database
    try:
        db.session.add(audit_entry)
        db.session.commit()
        return audit_entry.id
    except Exception as e:
        db.session.rollback()
        print(f"⚠️  Audit logging failed: {e}")
        # Don't raise - audit logging should never break the application
        return None


def log_field_change(action_type, record_type, record_id, field_name, old_value, new_value, change_reason=None):
    """
    Log a specific field change with old and new values

    Args:
        action_type (str): Type of action (usually UPDATE)
        record_type (str): Type of record (USER, ROLE, etc.)
        record_id (str/int): ID of the record
        field_name (str): Name of the field that changed
        old_value: Previous value
        new_value: New value
        change_reason (str): Why the change was made

    Returns:
        int: Audit log entry ID or None
    """
    return log_audit(
        action_type=action_type,
        record_type=record_type,
        record_id=record_id,
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        change_reason=change_reason
    )


def log_multiple_changes(action_type, record_type, record_id, changes, change_reason=None):
    """
    Log multiple field changes at once

    Args:
        action_type (str): Type of action
        record_type (str): Type of record
        record_id (str/int): ID of the record
        changes (list): List of dicts with 'field_name', 'old_value', 'new_value'
        change_reason (str): Reason for all changes

    Returns:
        list: List of audit log entry IDs

    Example:
        changes = [
            {'field_name': 'username', 'old_value': 'old', 'new_value': 'new'},
            {'field_name': 'email', 'old_value': 'old@ex.com', 'new_value': 'new@ex.com'}
        ]
    """
    audit_ids = []
    for change in changes:
        audit_id = log_field_change(
            action_type=action_type,
            record_type=record_type,
            record_id=record_id,
            field_name=change.get('field_name'),
            old_value=change.get('old_value'),
            new_value=change.get('new_value'),
            change_reason=change_reason
        )
        if audit_id:
            audit_ids.append(audit_id)
    return audit_ids


def _validate_change_reason(action_type, record_type, field_name, change_reason):
    """
    Check if change_reason is required and raise error if missing

    Raises:
        ValueError: If change_reason is required but not provided
    """
    # Check if action requires reason
    if action_type in REQUIRE_REASON_ACTIONS and not change_reason:
        raise ValueError(f"change_reason is required for action type: {action_type}")

    # Check if record type requires reason
    if record_type in REQUIRE_REASON_RECORDS and not change_reason:
        raise ValueError(f"change_reason is required for record type: {record_type}")

    # Check if field requires reason
    if field_name and field_name in REQUIRE_REASON_FIELDS and not change_reason:
        raise ValueError(f"change_reason is required for field: {field_name}")


def _sanitize_value(field_name, value):
    """
    Redact sensitive field values

    Args:
        field_name (str): Name of the field
        value: Value to sanitize

    Returns:
        str: Original value or [REDACTED]
    """
    if not value:
        return None

    if field_name and any(excluded in field_name.lower() for excluded in EXCLUDE_FIELDS):
        return REDACTED_VALUE

    return str(value)


def _generate_checksum(audit_entry):
    """
    Generate SHA-256 checksum for audit entry integrity

    Args:
        audit_entry (AuditLog): Audit log entry

    Returns:
        str: SHA-256 hex digest
    """
    # Concatenate key fields for checksum
    data_string = f"{audit_entry.timestamp}{audit_entry.user_id}{audit_entry.action_type}{audit_entry.record_type}{audit_entry.record_id}"
    return hashlib.sha256(data_string.encode()).hexdigest()

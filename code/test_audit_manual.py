"""
Manual test script for audit logging functions
Run this to verify audit trail is working before integrating with auth.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from audit_trail import log_audit, log_field_change
from audit_config import ACTION_LOGIN, ACTION_UPDATE, RECORD_USER, RECORD_PASSWORD
from models import AuditLog


def test_basic_logging():
    """Test basic audit logging"""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("Testing Basic Audit Logging")
        print("=" * 60)

        # Test 1: Simple login log
        print("\nTest 1: Logging a login action...")
        audit_id = log_audit(
            action_type=ACTION_LOGIN,
            record_type=RECORD_USER,
            record_id=1,
            change_reason="Manual test login"
        )

        if audit_id:
            print(f"✓ Created audit entry ID: {audit_id}")
            entry = db.session.get(AuditLog, audit_id)
            print(f"  - Username: {entry.username}")
            print(f"  - Action: {entry.action_type}")
            print(f"  - Timestamp: {entry.timestamp}")
        else:
            print("✗ Failed to create audit entry")
            return False

        # Test 2: Field change log
        print("\nTest 2: Logging a field change...")
        audit_id = log_field_change(
            action_type=ACTION_UPDATE,
            record_type=RECORD_USER,
            record_id=1,
            field_name='username',
            old_value='old_user',
            new_value='new_user',
            change_reason='Manual test update'
        )

        if audit_id:
            print(f"✓ Created field change audit ID: {audit_id}")
            entry = db.session.get(AuditLog, audit_id)
            print(f"  - Field: {entry.field_name}")
            print(f"  - Old: {entry.old_value}")
            print(f"  - New: {entry.new_value}")
        else:
            print("✗ Failed to create field change audit")
            return False

        # Test 3: Password change (should be redacted)
        print("\nTest 3: Logging password change (should be redacted)...")
        audit_id = log_field_change(
            action_type=ACTION_UPDATE,
            record_type=RECORD_PASSWORD,
            record_id=1,
            field_name='password',
            old_value='old_secret_pass',
            new_value='new_secret_pass',
            change_reason='Password change test'
        )

        if audit_id:
            print(f"✓ Created password audit ID: {audit_id}")
            entry = db.session.get(AuditLog, audit_id)
            print(f"  - Old value: {entry.old_value} (should be [REDACTED])")
            print(f"  - New value: {entry.new_value} (should be [REDACTED])")

            if entry.old_value == '[REDACTED]' and entry.new_value == '[REDACTED]':
                print("  ✓ Password redaction working correctly!")
            else:
                print("  ✗ Password NOT redacted - security issue!")
                return False

        print("\n" + "=" * 60)
        print("All Tests Passed! ✓")
        print("=" * 60)
        return True


if __name__ == '__main__':
    success = test_basic_logging()
    exit(0 if success else 1)

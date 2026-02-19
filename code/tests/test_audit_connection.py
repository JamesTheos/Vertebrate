"""
Test suite for 21 CFR Part 11 audit trail Python integration
Test 5: Python connection and ORM functionality
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from models import AuditLog
from datetime import datetime, timezone

def test_audit_write():
    app = create_app()

    with app.app_context():
        # Create test audit entry
        test_entry = AuditLog(
            timestamp=datetime.now(timezone.utc),
            user_id=999,
            username='test_connection',
            action_type='CONNECTION_TEST',
            record_type='SYSTEM',
            ip_address='192.168.1.1',
            change_reason='Testing Python to PostgreSQL audit connection'
        )

        db.session.add(test_entry)
        db.session.commit()

        print(f"✓ Test audit entry created with ID: {test_entry.id}")

        # Read it back
        retrieved = AuditLog.query.filter_by(user_id=999).first()
        if retrieved:
            print(f"✓ Successfully retrieved: {retrieved.username} - {retrieved.action_type}")
            print(f"✓ Timestamp: {retrieved.timestamp}")
            print(f"✓ Change reason: {retrieved.change_reason}")
            return True
        else:
            print("✗ Failed to retrieve test entry")
            return False

if __name__ == '__main__':
    success = test_audit_write()
    exit(0 if success else 1)

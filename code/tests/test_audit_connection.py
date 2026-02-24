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
    """Test 5: Verify Python ORM can write and read audit entries"""
    app = create_app()

    with app.app_context():
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

        retrieved = AuditLog.query.filter_by(user_id=999).first()

        # Cleanup before asserting
        AuditLog.query.filter_by(user_id=999).delete()
        db.session.commit()

        assert retrieved is not None, "Failed to retrieve test audit entry"
        assert retrieved.username == 'test_connection', "Username mismatch"
        assert retrieved.action_type == 'CONNECTION_TEST', "Action type mismatch"


if __name__ == '__main__':
    import pytest
    raise SystemExit(pytest.main([__file__, '-v']))

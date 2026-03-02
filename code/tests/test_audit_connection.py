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
    """Test 5: Verify log_audit() can write and read audit entries via ORM."""
    app = create_app()

    with app.app_context():
        from audit_trail import log_audit
        entry_id = log_audit(
            action_type='CONNECTION_TEST',
            record_type='SYSTEM',
            record_id='connection-test-entry',
            change_reason='Testing Python to PostgreSQL audit connection'
        )
        assert entry_id is not None, "log_audit() returned None — write failed"

        retrieved = AuditLog.query.filter_by(
            record_id='connection-test-entry'
        ).first()

        assert retrieved is not None, "Failed to retrieve test audit entry"
        assert retrieved.username is not None, "Username must not be NULL"
        assert retrieved.action_type == 'CONNECTION_TEST', "Action type mismatch"
        assert retrieved.checksum is not None, "Checksum must not be NULL"
        # No cleanup — audit rows are immutable by design (21 CFR Part 11)


if __name__ == '__main__':
    import pytest
    raise SystemExit(pytest.main([__file__, '-v']))

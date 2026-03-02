"""
Test suite for 21 CFR Part 11 audit trail database setup
Tests 1-4: Schema and table verification
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app, db
from sqlalchemy import text, inspect
from models import AuditLog


def test_schema_exists():
    """Test 1: Verify audit_trail schema exists"""
    app = create_app()
    with app.app_context():
        result = db.session.execute(text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name = 'audit_trail'"
        ))
        schemas = [row[0] for row in result]
        assert 'audit_trail' in schemas, "audit_trail schema does not exist"


def test_table_exists():
    """Test 2: Verify audit_logs table exists"""
    app = create_app()
    with app.app_context():
        result = db.session.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'audit_trail' AND table_name = 'audit_logs'"
        ))
        tables = [row[0] for row in result]
        assert 'audit_logs' in tables, "audit_logs table not found"


def test_table_structure():
    """Test 3: Verify audit_logs has all required columns"""
    app = create_app()
    required_columns = [
        'id', 'timestamp', 'user_id', 'username',
        'action_type', 'record_type', 'record_id',
        'field_name', 'old_value', 'new_value',
        'change_reason', 'ip_address', 'session_id',
        'request_method', 'endpoint', 'checksum'
    ]
    with app.app_context():
        inspector = inspect(db.engine)
        columns = inspector.get_columns('audit_logs', schema='audit_trail')
        column_names = [col['name'] for col in columns]
        missing = [col for col in required_columns if col not in column_names]
        assert not missing, f"Missing columns: {missing}"


def test_no_audit_entry_has_null_checksum():
    """21 CFR Part 11: every audit row must have a checksum — no exceptions."""
    app = create_app()
    with app.app_context():
        null_rows = AuditLog.query.filter(AuditLog.checksum == None).all()
        null_ids = [r.id for r in null_rows]
        assert len(null_rows) == 0, \
            f"{len(null_rows)} audit entries missing checksum (IDs: {null_ids})"


def test_manual_insert():
    """Test 4: Verify log_audit() can write and query records via ORM."""
    app = create_app()
    with app.app_context():
        from audit_trail import log_audit
        entry_id = log_audit(
            action_type='CONNECTION_TEST',
            record_type='SYSTEM',
            record_id='manual-insert-test',
            change_reason='Testing audit write via log_audit()'
        )
        assert entry_id is not None, "log_audit() returned None — write failed"

        retrieved = AuditLog.query.filter_by(record_id='manual-insert-test').first()
        assert retrieved is not None, "Failed to retrieve inserted audit entry"
        assert retrieved.action_type == 'CONNECTION_TEST', "Action type mismatch"
        assert retrieved.checksum is not None, "Checksum must not be NULL"
        # No cleanup — audit rows are immutable by design (21 CFR Part 11)


if __name__ == '__main__':
    import pytest
    raise SystemExit(pytest.main([__file__, '-v']))

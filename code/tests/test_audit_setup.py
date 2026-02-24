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


def test_manual_insert():
    """Test 4: Verify can insert and query records"""
    app = create_app()
    with app.app_context():
        db.session.execute(text(
            "INSERT INTO audit_trail.audit_logs "
            "(timestamp, user_id, username, action_type, record_type, ip_address) "
            "VALUES (NOW(), 1, 'test_user', 'TEST', 'MANUAL_TEST', '127.0.0.1')"
        ))
        db.session.commit()

        result = db.session.execute(text(
            "SELECT id, username, action_type FROM audit_trail.audit_logs "
            "WHERE action_type = 'TEST' LIMIT 1"
        ))
        row = result.fetchone()

        # Cleanup before asserting so DB stays clean even on failure
        db.session.execute(text(
            "DELETE FROM audit_trail.audit_logs WHERE action_type = 'TEST'"
        ))
        db.session.commit()

        assert row is not None, "Failed to retrieve inserted record"
        assert row[1] == 'test_user', "Username mismatch"


if __name__ == '__main__':
    import pytest
    raise SystemExit(pytest.main([__file__, '-v']))

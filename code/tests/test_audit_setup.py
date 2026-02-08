"""
Test suite for 21 CFR Part 11 audit trail database setup
Tests 1-4: Schema and table verification
"""

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

        assert 'audit_trail' in schemas, "audit_trail schema not found"
        print("✓ Test 1 PASS: audit_trail schema exists")
        return True


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
        print("✓ Test 2 PASS: audit_logs table exists")
        return True


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

        print(f"✓ Test 3 PASS: All {len(required_columns)} columns present")
        return True


def test_manual_insert():
    """Test 4: Verify can insert and query records"""
    app = create_app()

    with app.app_context():
        # Insert test record
        db.session.execute(text(
            "INSERT INTO audit_trail.audit_logs "
            "(timestamp, user_id, username, action_type, record_type, ip_address) "
            "VALUES (NOW(), 1, 'test_user', 'TEST', 'MANUAL_TEST', '127.0.0.1')"
        ))
        db.session.commit()

        # Query it back
        result = db.session.execute(text(
            "SELECT id, username, action_type FROM audit_trail.audit_logs "
            "WHERE action_type = 'TEST' LIMIT 1"
        ))
        row = result.fetchone()

        assert row is not None, "Failed to retrieve inserted record"
        assert row[1] == 'test_user', "Username mismatch"

        # Cleanup
        db.session.execute(text(
            "DELETE FROM audit_trail.audit_logs WHERE action_type = 'TEST'"
        ))
        db.session.commit()

        print("✓ Test 4 PASS: Can insert and query records")
        return True


def run_all_setup_tests():
    """Run all setup tests (1-4)"""
    print("\n=== Running Audit Trail Setup Tests ===\n")

    tests = [
        ("Schema exists", test_schema_exists),
        ("Table exists", test_table_exists),
        ("Table structure", test_table_structure),
        ("Manual insert/query", test_manual_insert)
    ]

    results = []
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, True))
        except Exception as e:
            print(f"✗ Test FAIL: {name} - {e}")
            results.append((name, False))

    print("\n=== Test Results ===")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    return all(result for _, result in results)


if __name__ == '__main__':
    success = run_all_setup_tests()
    exit(0 if success else 1)

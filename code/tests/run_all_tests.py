"""
Test runner for 21 CFR Part 11 audit trail tests.
Delegates entirely to pytest — use this script for convenience or CI entry point.

Usage:
    # Run all tests (SQLite, skips postgres_only):
    python code/tests/run_all_tests.py

    # Run including PostgreSQL-specific tests (requires live Postgres):
    SQLALCHEMY_DATABASE_URI=postgresql://user:pass@localhost:5432/vertebrate \
        python code/tests/run_all_tests.py
"""

import sys
import os
import pytest

# Ensure 'code/' is on the path regardless of invocation directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def run_all_tests():
    print("=" * 60)
    print("21 CFR Part 11 Audit Trail — Complete Test Suite")
    print("=" * 60)

    db_url = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///:memory:')
    backend = 'PostgreSQL' if 'postgresql' in db_url else 'SQLite (postgres_only tests will be skipped)'
    print(f"Database backend: {backend}\n")

    exit_code = pytest.main([
        TESTS_DIR,
        '-v',                    # verbose — show each test name and result
        '--tb=short',            # compact tracebacks on failure
        '--no-header',
        f'--rootdir={TESTS_DIR}',
    ])

    return exit_code == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
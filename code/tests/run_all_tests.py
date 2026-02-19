"""
Main test runner for 21 CFR Part 11 audit trail tests
Runs all tests in sequence
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_audit_setup import run_all_setup_tests
from test_audit_connection import test_audit_write


def run_all_tests():
    print("=" * 60)
    print("21 CFR Part 11 Audit Trail - Complete Test Suite")
    print("=" * 60)

    # Run setup tests (1-4)
    setup_success = run_all_setup_tests()

    # Run connection test (5)
    print("\n=== Running Python Integration Test ===\n")
    try:
        connection_success = test_audit_write()
        if connection_success:
            print("✓ Test 5 PASS: Python connection successful")
    except Exception as e:
        print(f"✗ Test 5 FAIL: {e}")
        connection_success = False

    # Summary
    print("\n" + "=" * 60)
    print("Test Suite Summary")
    print("=" * 60)
    print(f"Setup Tests (1-4): {'PASS ✓' if setup_success else 'FAIL ✗'}")
    print(f"Connection Test (5): {'PASS ✓' if connection_success else 'FAIL ✗'}")

    all_pass = setup_success and connection_success
    print(f"\nOverall: {'ALL TESTS PASSED ✓' if all_pass else 'SOME TESTS FAILED ✗'}")

    return all_pass


if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)

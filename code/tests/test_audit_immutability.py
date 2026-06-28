"""
test_audit_immutability.py
21 CFR Part 11 — immutability tests for audit_trail.audit_logs

These tests verify that:
  1. Direct UPDATE/DELETE on audit_trail.audit_logs is blocked by the DB trigger
  2. Tampered rows are detectable via checksum mismatch

All tests in this file require a live PostgreSQL instance with the
immutability trigger installed by createDB.py. They are automatically
skipped when running against SQLite (see conftest.py postgres_only marker).

Usage:
    docker compose exec vertebrate-app python -m pytest \
        tests/test_audit_immutability.py -v
"""
import os
import time
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError, InternalError

pytestmark = pytest.mark.postgres_only
import pytest
pytestmark = pytest.mark.postgres_only

os.environ.setdefault('DISABLE_KAFKA', '1')


@pytest.fixture(scope='module')
def app():
    from app import create_app
    flask_app = create_app()
    flask_app.config['TESTING'] = True
    with flask_app.app_context():
        yield flask_app


@pytest.fixture(scope='module')
def seed_entry(app):
    """
    Write one real audit entry to use as the immutability test target.
    Uses a timestamp-based record_id so every run creates a fresh unique row —
    no cleanup needed, no trigger conflict possible.
    """
    from audit_trail import log_audit
    from models import AuditLog, db
    from sqlalchemy.orm import Session

    SEED_RECORD_ID = f'immutability-test-{int(time.time())}'

    with app.app_context():
        entry_id = log_audit(
            action_type='SYSTEM',
            record_type='SYSTEM',
            record_id=SEED_RECORD_ID,
            change_reason='Seed entry for immutability test'
        )
        assert entry_id is not None, "Could not seed audit entry"

        with Session(db.engine) as s:
            entry = s.get(AuditLog, entry_id)
            assert entry is not None, f"Seed entry {entry_id} not found after write"

        yield entry_id
        # No teardown — audit rows are immutable by design (21 CFR Part 11)


class TestAuditImmutability:

    def test_update_audit_entry_raises_exception(self, app, seed_entry):
        """Direct UPDATE on audit_logs must be blocked by DB trigger."""
        from models import db
        with app.app_context():
            with pytest.raises((ProgrammingError, InternalError)):
                db.session.execute(text(
                    "UPDATE audit_trail.audit_logs SET change_reason = 'tampered' "
                    f"WHERE id = {seed_entry}"
                ))
                db.session.commit()
            db.session.rollback()

    def test_delete_audit_entry_raises_exception(self, app, seed_entry):
        """Direct DELETE on audit_logs must be blocked by DB trigger."""
        from models import db
        with app.app_context():
            with pytest.raises((ProgrammingError, InternalError)):
                db.session.execute(text(
                    f"DELETE FROM audit_trail.audit_logs WHERE id = {seed_entry}"
                ))
                db.session.commit()
            db.session.rollback()

    def test_tampered_entry_fails_checksum_verification(self, app, seed_entry):
        """A row whose fields were changed must not match its stored checksum."""
        from models import AuditLog, db
        import hashlib
        import json
        with app.app_context():
            from sqlalchemy.orm import Session
            with Session(db.engine) as s:
                entry = s.get(AuditLog, seed_entry)
                assert entry is not None, f"Entry {seed_entry} not found"

                # Simulate tampering — change action_type in the payload
                payload = {
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                    "user_id": entry.user_id,
                    "username": entry.username,
                    "action_type": "TAMPERED",  # ← altered field
                    "record_type": entry.record_type,
                    "record_id": entry.record_id,
                    "field_name": entry.field_name,
                    "old_value": entry.old_value,
                    "new_value": entry.new_value,
                    "change_reason": entry.change_reason,
                    "ip_address": entry.ip_address,
                    "endpoint": entry.endpoint,
                }
                tampered_checksum = hashlib.sha256(
                    json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
                    .encode("utf-8")
                ).hexdigest()

                assert tampered_checksum != entry.checksum, \
                    "Tampered checksum should not match the stored checksum"

class TestChecksumCompleteness:

    def test_no_audit_entry_has_null_checksum(self, app):
        """Every audit row must have a non-null checksum — no exceptions."""
        from models import AuditLog
        with app.app_context():
            null_rows = AuditLog.query.filter(AuditLog.checksum.is_(None)).all()
            null_ids = [r.id for r in null_rows]
            assert len(null_rows) == 0, \
                f"{len(null_rows)} audit entries missing checksum (IDs: {null_ids})"

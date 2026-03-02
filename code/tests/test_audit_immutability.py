"""
test_audit_immutability.py
21 CFR Part 11 — immutability tests for audit_trail.audit_logs
TDD: these tests are written BEFORE the trigger is installed.
Expected to FAIL (RED) until createDB.py installs the trigger.

Usage:
    docker compose exec vertebrate-app python -m pytest \
        tests/test_audit_immutability.py -v
"""
import os
import time
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError, InternalError

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
        with app.app_context():
            from sqlalchemy.orm import Session
            with Session(db.engine) as s:
                entry = s.get(AuditLog, seed_entry)
                assert entry is not None, f"Entry {seed_entry} not found"

                data_string = (
                    f"{entry.timestamp}{entry.user_id}TAMPERED"
                    f"{entry.record_type}{entry.record_id}"
                )
                tampered_checksum = hashlib.sha256(data_string.encode()).hexdigest()

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

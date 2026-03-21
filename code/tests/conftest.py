import os
import sys
import pytest

# ── Environment setup ────────────────────────────────────────────────────────
# Must happen BEFORE any app imports.

os.environ['DISABLE_KAFKA'] = '1'

# Only fall back to SQLite if no external DB is configured.
# This allows Docker/CI runs against Postgres to work without being overridden.
os.environ.setdefault('SQLALCHEMY_DATABASE_URI', 'sqlite:///:memory:')

# Make 'code/' importable regardless of where pytest is invoked from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app   # noqa: E402
from models import db as _db  # noqa: E402


# ── Dialect helpers ──────────────────────────────────────────────────────────

def _is_postgres(app):
    return app.config.get('SQLALCHEMY_DATABASE_URI', '').startswith('postgresql')


# ── Markers ──────────────────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "postgres_only: mark test as requiring a live PostgreSQL database"
    )


def pytest_collection_modifyitems(config, items):
    """Skip postgres_only tests when running against SQLite."""
    for item in items:
        if item.get_closest_marker('postgres_only'):
            db_url = os.environ.get('SQLALCHEMY_DATABASE_URI', '')
            if 'postgresql' not in db_url and 'postgres' not in db_url:
                item.add_marker(
                    pytest.mark.skip(
                        reason="Requires PostgreSQL — set SQLALCHEMY_DATABASE_URI to a Postgres URL to run"
                    )
                )


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'
    with app.app_context():
        if _is_postgres(app):
            # Create audit_trail schema before create_all so AuditLog table lands correctly
            from sqlalchemy import text
            try:
                _db.session.execute(text('CREATE SCHEMA IF NOT EXISTS audit_trail'))
                _db.session.commit()
            except Exception:
                _db.session.rollback()
        _db.create_all()
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    with app.app_context():
        yield _db
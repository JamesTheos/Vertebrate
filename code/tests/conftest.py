import os
import sqlite3
import sys
import pytest

from sqlalchemy import event
from sqlalchemy.engine import Engine

# ── Environment setup ────────────────────────────────────────────────────────
# Must happen BEFORE any app imports.

os.environ['DISABLE_KAFKA'] = '1'

# Tests are driven SOLELY by SQLALCHEMY_DATABASE_URI.  Remove any DATABASE_URL
# first: inside the Docker app container it points at the live Postgres DB, and
# create_app() resolves `DATABASE_URL or SQLALCHEMY_DATABASE_URI` — so leaving it
# set would route the whole suite (including destructive fixtures) at the real
# database.  See test_db_isolation.py for the regression guard.
os.environ.pop('DATABASE_URL', None)

# Default to an isolated in-memory SQLite DB.  To run @pytest.mark.postgres_only
# tests, set SQLALCHEMY_DATABASE_URI to a Postgres URL explicitly.
os.environ.setdefault('SQLALCHEMY_DATABASE_URI', 'sqlite:///:memory:')

# Make 'code/' importable regardless of where pytest is invoked from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app   # noqa: E402
from models import db as _db  # noqa: E402


# ── SQLite audit-schema shim ──────────────────────────────────────────────────
# The AuditLog model lives in the PostgreSQL schema `audit_trail`
# (models.py: __table_args__ = {'schema': 'audit_trail'}).  SQLite has no schema
# concept, so create_all() of `audit_trail.audit_logs` fails with
# "unknown database audit_trail".  ATTACH an in-memory DB under that name on every
# SQLite connection so the schema-qualified table resolves.  No-op on Postgres.
@event.listens_for(Engine, "connect")
def _attach_audit_schema_on_sqlite(dbapi_conn, _conn_record):
    if isinstance(dbapi_conn, sqlite3.Connection):
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS audit_trail")


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

# Path to the real config.json the app reads (code/config.json), resolved
# relative to this file (code/tests/conftest.py).
_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json'
)


@pytest.fixture(autouse=True)
def _preserve_config_json():
    """Snapshot config.json before each test and restore it afterward.

    Routes such as /save-plant-config write to the real config.json on disk.  A
    test that mutates it and doesn't restore leaves the file corrupted — and if
    required keys (Kafkaserver, clusterid, assets) are dropped the app crashes on
    next startup.  Restoring keeps every test starting from a pristine file.
    """
    try:
        with open(_CONFIG_PATH, 'rb') as f:
            original = f.read()
    except FileNotFoundError:
        original = None
    yield
    if original is not None:
        with open(_CONFIG_PATH, 'wb') as f:
            f.write(original)


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
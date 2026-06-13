"""
test_db_isolation.py

Regression guard: the test suite must never run against the live database.

Inside the Docker app container, DATABASE_URL points at the production Postgres
instance.  create_app() resolves the DB as `DATABASE_URL or
SQLALCHEMY_DATABASE_URI` (app.py), so without isolation the entire suite —
including destructive fixtures such as test_routes.clean_db — would execute
against, and wipe, the live database.

conftest.py must neutralise DATABASE_URL so tests resolve to the SQLite URI
unless an operator has *explicitly* aimed them at Postgres via
SQLALCHEMY_DATABASE_URI (the documented knob for @pytest.mark.postgres_only).
"""

import os


def test_database_url_does_not_leak_into_test_app(app):
    """create_app() under test must not pick up a stray DATABASE_URL.

    If an operator explicitly set SQLALCHEMY_DATABASE_URI to Postgres (to run
    postgres_only tests), the app may legitimately be on Postgres.  Otherwise it
    must be SQLite — a Postgres URI here means DATABASE_URL leaked in.
    """
    resolved = app.config['SQLALCHEMY_DATABASE_URI']
    explicit = os.environ.get('SQLALCHEMY_DATABASE_URI', '')

    if 'postgres' in explicit:
        # Operator deliberately targeted Postgres — that's allowed.
        assert resolved == explicit
    else:
        assert resolved.startswith('sqlite'), (
            f"Test app resolved to {resolved!r}, not SQLite. "
            "A production DATABASE_URL has leaked into the test harness; "
            "conftest must pop it before importing the app."
        )


def test_conftest_removes_production_database_url():
    """conftest must remove DATABASE_URL from the environment at import time."""
    assert os.environ.get('DATABASE_URL') is None, (
        "DATABASE_URL is still set during tests; create_app() will route the "
        "suite at the live database. conftest must os.environ.pop it."
    )

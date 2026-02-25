import os
import sys
import pytest

# Set test environment BEFORE importing anything
os.environ['DISABLE_KAFKA'] = '1'
os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

# Make 'code/' importable regardless of where pytest is invoked from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from models import db as _db  # noqa: E402


@pytest.fixture(scope="session")
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'
    with app.app_context():
        _db.create_all()
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    with app.app_context():
        yield _db

import os
import pytest

# Ensure Kafka setup is disabled before importing the app module
os.environ.setdefault('DISABLE_KAFKA', '1')

from code.app import create_app  # noqa: E402
from code.models import db as _db  # noqa: E402


@pytest.fixture(scope="session")
def app():
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SECRET_KEY': 'test-secret'
    })
    with app.app_context():
        _db.create_all()
    yield app
    # no explicit teardown needed for in-memory


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    # Provide the database handle within an application context
    with app.app_context():
        yield _db

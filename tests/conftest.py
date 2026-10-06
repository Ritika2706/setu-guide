import pytest
from fastapi.testclient import TestClient

from app.api.main import app


@pytest.fixture(scope="session")
def client():
    """Default client: unhandled exceptions are surfaced so tests can see them."""
    return TestClient(app)


@pytest.fixture(scope="session")
def client_no_raise():
    """Client used by the 500 test, where an unhandled exception is expected."""
    return TestClient(app, raise_server_exceptions=False)

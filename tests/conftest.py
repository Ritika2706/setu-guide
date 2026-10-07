import pytest
from fastapi.testclient import TestClient

from app.api.cache import response_cache
from app.api.main import app
from app.api.ratelimit import limiter
from app.config import get_settings


@pytest.fixture(scope="session")
def client():
    """Default client: unhandled exceptions are surfaced so tests can see them."""
    return TestClient(app)


@pytest.fixture(scope="session")
def client_no_raise():
    """Client used by the 500 test, where an unhandled exception is expected."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def fresh_state():
    """Counters and cache start empty for every test, so a limit or a HIT
    created by one test can never leak into the next one."""
    for clear in (limiter.reset, response_cache.clear, get_settings.cache_clear):
        clear()
    yield
    for clear in (limiter.reset, response_cache.clear, get_settings.cache_clear):
        clear()


@pytest.fixture
def set_env(monkeypatch):
    """Set environment variables and drop the cached settings.

    Call get_settings() yourself when you expect it to raise.
    """
    def _set(**env_vars):
        for name, value in env_vars.items():
            monkeypatch.setenv(name, str(value))
        get_settings.cache_clear()
    yield _set
    get_settings.cache_clear()

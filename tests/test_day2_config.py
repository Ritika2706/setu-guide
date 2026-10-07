"""Day 2: configuration comes from the environment and fails fast when unusable."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import Settings, SettingsError, get_settings, parse_rate_limit

REPO_ROOT = Path(__file__).resolve().parents[1]
CHAT = "/v1/guide/chat"


def test_mock_mode_starts_without_a_key(client, set_env):
    set_env(USE_MOCK="true", LLM_API_KEY="")
    settings = get_settings()
    assert settings.use_mock is True
    assert not settings.llm_api_key
    assert client.get("/health").json() == {"status": "ok"}


def test_real_mode_without_key_fails_with_clear_message(set_env):
    set_env(USE_MOCK="false", LLM_API_KEY="")
    with pytest.raises(SettingsError) as exc:
        get_settings()
    message = str(exc.value)
    assert "LLM_API_KEY" in message
    assert "USE_MOCK=false" in message


def test_real_mode_with_key_is_accepted(set_env):
    set_env(USE_MOCK="false", LLM_API_KEY="dummy-key-for-tests")
    assert get_settings().use_mock is False


def test_startup_process_dies_without_key_in_real_mode():
    """Importing the app (what uvicorn does) must exit non-zero with a clear line."""
    env = {k: v for k, v in os.environ.items() if k != "LLM_API_KEY"}
    env["USE_MOCK"] = "false"
    env["LLM_API_KEY"] = ""  # an empty value also beats a local .env file
    proc = subprocess.run([sys.executable, "-c", "import app.api.main"],
                          cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert proc.returncode != 0, "startup should fail when real mode has no key"
    assert "LLM_API_KEY" in (proc.stderr + proc.stdout)


def test_all_values_come_from_the_environment(set_env):
    set_env(USE_MOCK="true", LLM_PROVIDER="acme", LLM_TIMEOUT_SECONDS="7.5",
            RATE_LIMIT_PER_USER="5/minute", RATE_LIMIT_PER_IP="10/second",
            CACHE_ENABLED="false", CACHE_TTL_SECONDS="30", CACHE_MAX_ITEMS="10",
            TRUSTED_PROXY="true", LOG_LEVEL="debug")
    settings = get_settings()
    assert settings.llm_provider == "acme"
    assert settings.llm_timeout_seconds == 7.5
    assert settings.user_limit == (5, 60)
    assert settings.ip_limit == (10, 1)
    assert settings.cache_enabled is False
    assert settings.cache_ttl_seconds == 30
    assert settings.cache_max_items == 10
    assert settings.trusted_proxy is True
    assert settings.log_level == "DEBUG"  # normalised


def test_placeholder_defaults(monkeypatch):
    """Day 2 placeholder values, read with any local .env switched off."""
    for var in ("USE_MOCK", "LLM_API_KEY", "LLM_PROVIDER", "LLM_TIMEOUT_SECONDS",
                "RATE_LIMIT_PER_USER", "RATE_LIMIT_PER_IP", "CACHE_ENABLED",
                "CACHE_TTL_SECONDS", "CACHE_MAX_ITEMS", "TRUSTED_PROXY", "LOG_LEVEL"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)
    assert settings.use_mock is True
    assert settings.llm_provider == "placeholder"
    assert settings.llm_timeout_seconds == 10.0
    assert settings.rate_limit_per_user == "30/minute"
    assert settings.rate_limit_per_ip == "60/minute"
    assert settings.cache_enabled is True
    assert settings.cache_ttl_seconds == 600
    assert settings.cache_max_items == 500
    assert settings.trusted_proxy is False
    assert settings.log_level == "INFO"

    # The secret must never appear in repr() (that is what loggers print).
    with_key = Settings(_env_file=None, llm_api_key="sk-HIDDEN-VALUE")
    assert "sk-HIDDEN-VALUE" not in repr(with_key)
    assert "sk-HIDDEN-VALUE" not in str(with_key)


@pytest.mark.parametrize("spec,expected", [
    ("30/minute", (30, 60)),
    ("10", (10, 60)),
    ("5/second", (5, 1)),
    ("2/hour", (2, 3600)),
    ("1/day", (1, 86400)),
])
def test_parse_rate_limit(spec, expected):
    assert parse_rate_limit(spec) == expected


@pytest.mark.parametrize("field", ["RATE_LIMIT_PER_USER", "RATE_LIMIT_PER_IP"])
def test_invalid_rate_limit_fails_at_startup(set_env, field):
    set_env(**{field: "banana"})
    with pytest.raises(SettingsError) as exc:
        get_settings()
    assert "rate limit" in str(exc.value)


def test_invalid_log_level_fails_at_startup(set_env):
    set_env(LOG_LEVEL="LOUD")
    with pytest.raises(SettingsError) as exc:
        get_settings()
    assert "LOG_LEVEL" in str(exc.value)


def test_secret_is_never_printed_in_errors(set_env):
    """A config failure while a secret is set must not echo the secret."""
    set_env(USE_MOCK="false", LLM_API_KEY="sk-SUPER-SECRET-VALUE", RATE_LIMIT_PER_IP="banana")
    with pytest.raises(SettingsError) as exc:
        get_settings()
    assert "sk-SUPER-SECRET-VALUE" not in str(exc.value)
    assert "rate limit" in str(exc.value)

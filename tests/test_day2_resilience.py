"""Day 2: LLM failure safety net (never error the client) and log hygiene."""
import json
import logging
import time

from app.core import orchestrator
from app.schemas.guide import GuideRequest

CHAT = "/v1/guide/chat"
QUICK_ACTION = {"user_id": "u1", "match_id": "m1", "stage": "connect", "intent": "next_steps"}


def _real_mode(client, set_env, monkeypatch, entry, **extra):
    set_env(USE_MOCK="false", LLM_API_KEY="dummy-key-for-tests", **extra)
    monkeypatch.setattr(orchestrator, "handle_chat", entry, raising=False)
    return client.post(CHAT, json=QUICK_ACTION)


# ---------------------------------------------------------------- safety net

def test_orchestrator_exception_returns_200_fallback(client, set_env, monkeypatch):
    def boom(_req):
        raise RuntimeError("llm exploded")

    r = _real_mode(client, set_env, monkeypatch, boom)
    assert r.status_code == 200
    body = r.json()
    assert body["fallback_used"] is True
    assert body["safety"]["status"] == "pass"
    assert body["safety"]["flags"] == []
    assert body["reply"]
    assert r.headers["X-Cache"] == "MISS"


def test_orchestrator_timeout_returns_200_fallback(client, set_env, monkeypatch):
    def slow(_req):
        time.sleep(1.0)
        return GuideRequest  # never reached

    monkeypatch.setattr("app.api.chat.TIMEOUT_MARGIN_SECONDS", 0.0)
    started = time.monotonic()
    r = _real_mode(client, set_env, monkeypatch, slow, LLM_TIMEOUT_SECONDS="0.05")
    elapsed = time.monotonic() - started
    assert r.status_code == 200
    assert r.json()["fallback_used"] is True
    assert r.json()["safety"] == {"status": "pass", "flags": []}
    assert elapsed < 0.9, f"timeout not enforced, took {elapsed:.2f}s"


def test_orchestrator_failure_is_not_cached(client, set_env, monkeypatch):
    def boom(_req):
        raise RuntimeError("llm exploded")

    first = _real_mode(client, set_env, monkeypatch, boom)
    second = client.post(CHAT, json=QUICK_ACTION)
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "MISS"
    assert second.json()["fallback_used"] is True


def test_missing_handle_chat_is_reported_as_fallback_not_error(client, set_env):
    """Real mode before the lead ships handle_chat: still a 200, never a 500."""
    set_env(USE_MOCK="false", LLM_API_KEY="dummy-key-for-tests")
    r = client.post(CHAT, json=QUICK_ACTION)
    assert r.status_code == 200
    assert r.json()["fallback_used"] is True


def test_mock_mode_still_returns_the_day1_reply(client, set_env):
    set_env(USE_MOCK="true")
    body = client.post(CHAT, json=QUICK_ACTION).json()
    assert body["reply"] == "(mock reply)"
    assert body["fallback_used"] is False


# --------------------------------------------------------------------- logs

def _access_log_lines(caplog):
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("http_request ")]


def test_logs_carry_the_required_fields_without_private_data(client, set_env, caplog):
    set_env(USE_MOCK="true", LLM_API_KEY="sk-SECRET-MUST-NOT-APPEAR", LOG_LEVEL="INFO")
    payload = {**QUICK_ACTION, "user_id": "secret-user-42", "match_id": "secret-match-42",
               "message": "PRIVATE MESSAGE TEXT ABCXYZ", "topic": "private topic qqq"}
    with caplog.at_level(logging.INFO, logger="setu.guide"):
        r = client.post(CHAT, json=payload)

    assert r.status_code == 200
    lines = _access_log_lines(caplog)
    assert lines, "no structured access log line was produced"

    entry = json.loads(lines[0].split("http_request ", 1)[1])
    assert entry["request_id"] == r.headers["X-Request-Id"]
    assert entry["method"] == "POST"
    assert entry["path"] == CHAT
    assert entry["status"] == 200
    assert isinstance(entry["latency_ms"], (int, float))
    assert entry["cache"] == "MISS"
    assert entry["intent"] == "next_steps"
    assert entry["stage"] == "connect"
    assert entry["fallback_used"] is False

    logged = caplog.text
    assert "PRIVATE MESSAGE TEXT ABCXYZ" not in logged
    assert "private topic qqq" not in logged
    assert "secret-user-42" not in logged
    assert "secret-match-42" not in logged
    assert "sk-SECRET-MUST-NOT-APPEAR" not in logged


def test_error_logs_do_not_echo_the_input(client, set_env, caplog):
    set_env(LOG_LEVEL="INFO")
    with caplog.at_level(logging.INFO, logger="setu.guide"):
        client.post(CHAT, json={"user_id": "u", "match_id": "m", "stage": "ZZ-LEAK-STAGE"})
    assert "ZZ-LEAK-STAGE" not in caplog.text


def test_rate_limit_log_names_the_scope_but_not_the_user(client, set_env, caplog):
    set_env(RATE_LIMIT_PER_USER="1/minute", RATE_LIMIT_PER_IP="1000/minute", LOG_LEVEL="INFO")
    client.post(CHAT, json=QUICK_ACTION)
    with caplog.at_level(logging.INFO, logger="setu.guide"):
        client.post(CHAT, json=QUICK_ACTION)
    assert "rate_limited scope=user" in caplog.text
    assert "u1" not in caplog.text

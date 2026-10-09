"""Day 3: orchestrator (LLM) failure modes must never surface as an error.

Runs in real mode (USE_MOCK=false). app/core belongs to the AI/ML team, so
nothing there is edited: a fake `handle_chat` is planted with monkeypatch for
the duration of a single test, exactly like Day 2 does.

Expected contract for every LLM failure (timeout, exception, invalid schema,
missing entry point):
    HTTP 200, template reply, fallback_used=true, safety.status="pass",
    flags=[], and the fallback reply is NEVER cached.
"""
import time

from app.api.chat import FALLBACK_REPLY
from app.core import orchestrator

CHAT = "/v1/guide/chat"
QUICK_ACTION = {"user_id": "day3_llm_u1", "match_id": "day3_llm_m1",
                "stage": "reflect", "intent": "next_steps"}


def _real_mode(client, set_env, monkeypatch, entry=None, **extra):
    """USE_MOCK=false + (optionally) a fake orchestrator entry point."""
    set_env(USE_MOCK="false", LLM_API_KEY="dummy-key-for-tests", **extra)
    if entry is not None:
        monkeypatch.setattr(orchestrator, "handle_chat", entry, raising=False)
    return client.post(CHAT, json=QUICK_ACTION)


def assert_safe_fallback(r):
    assert r.status_code == 200, f"LLM failure leaked as HTTP {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert body["fallback_used"] is True
    assert body["reply"] == FALLBACK_REPLY
    assert body["safety"]["status"] == "pass"
    assert body["safety"]["flags"] == []
    assert r.headers["X-Cache"] == "MISS"
    return body


# ------------------------------------------------------------ failure modes

def test_llm_timeout_returns_template_reply(client, set_env, monkeypatch):
    def slow(_req):
        time.sleep(1.0)  # far above LLM_TIMEOUT_SECONDS below

    monkeypatch.setattr("app.api.chat.TIMEOUT_MARGIN_SECONDS", 0.0)
    started = time.monotonic()
    r = _real_mode(client, set_env, monkeypatch, slow, LLM_TIMEOUT_SECONDS="0.05")
    elapsed = time.monotonic() - started
    assert_safe_fallback(r)
    assert elapsed < 0.9, f"timeout not enforced, took {elapsed:.2f}s"


def test_llm_exception_returns_template_reply(client, set_env, monkeypatch):
    def boom(_req):
        raise RuntimeError("provider exploded with SECRET-LLM-TEXT")

    r = _real_mode(client, set_env, monkeypatch, boom)
    assert_safe_fallback(r)
    assert "SECRET-LLM-TEXT" not in r.text, "exception text leaked into the response"


def test_llm_returns_invalid_schema(client, set_env, monkeypatch):
    """Wrong-shaped object (bad enum value, wrong reply type) -> fallback."""
    def invalid_dict(_req):
        return {"intent": "not-a-real-intent", "reply": 12345}

    r = _real_mode(client, set_env, monkeypatch, invalid_dict)
    assert_safe_fallback(r)


def test_llm_returns_invalid_json_string(client, set_env, monkeypatch):
    """Orchestrator hands back a truncated JSON string -> fallback, not 500."""
    def broken_json(_req):
        return '{"intent": "next_steps", "reply": '

    r = _real_mode(client, set_env, monkeypatch, broken_json)
    assert_safe_fallback(r)


def test_llm_returns_wrong_type(client, set_env, monkeypatch):
    def wrong_type(_req):
        return 42

    r = _real_mode(client, set_env, monkeypatch, wrong_type)
    assert_safe_fallback(r)


def test_handle_chat_not_implemented_yet(client, set_env):
    """Real mode before the lead ships handle_chat: still 200, never a 500."""
    set_env(USE_MOCK="false", LLM_API_KEY="dummy-key-for-tests")
    assert_safe_fallback(client.post(CHAT, json=QUICK_ACTION))


def test_fallback_reply_is_not_cached(client, set_env, monkeypatch):
    """Two identical quick actions while the LLM is down: both MISS."""
    def boom(_req):
        raise RuntimeError("llm down")

    first = _real_mode(client, set_env, monkeypatch, boom)
    second = client.post(CHAT, json=QUICK_ACTION)
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "MISS"
    assert second.json()["fallback_used"] is True


def test_service_recovers_once_the_llm_works_again(client, set_env, monkeypatch):
    """A fallback must not stick: the next healthy reply is served normally."""
    def boom(_req):
        raise RuntimeError("llm down")

    _real_mode(client, set_env, monkeypatch, boom)

    def healthy(_req):
        from app.schemas.guide import GuideResponse, Intent
        return GuideResponse(intent=Intent.next_steps, reply="recovered reply")

    monkeypatch.setattr(orchestrator, "handle_chat", healthy, raising=False)
    r = client.post(CHAT, json=QUICK_ACTION)
    assert r.status_code == 200
    body = r.json()
    assert body["fallback_used"] is False
    assert body["reply"] == "recovered reply"


# ------------------------------------------------- unexpected internal error

def test_unexpected_exception_is_500_without_internal_details(client_no_raise, set_env, monkeypatch):
    """Mock path raising an unhandled bug: 500 + internal_error, and the
    response body carries no stack trace, no file names, no exception text."""
    set_env(USE_MOCK="true")

    def broken_handler(_req):
        raise RuntimeError("INTERNAL-DETAIL-MARKER-must-not-leak")

    monkeypatch.setattr("app.api.main.handle", broken_handler)
    r = client_no_raise.post(CHAT, json=QUICK_ACTION)
    assert r.status_code == 500
    body = r.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["details"] == []
    assert "Traceback" not in r.text
    assert "INTERNAL-DETAIL-MARKER" not in r.text
    assert "File \"" not in r.text
    assert "RuntimeError" not in r.text

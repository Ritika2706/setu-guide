"""Day 2: response caching rules (what may be cached, and the X-Cache header)."""
from app.core import orchestrator
from app.core.orchestrator import handle as real_handle

CHAT = "/v1/guide/chat"
QUICK_ACTION = {"user_id": "u1", "match_id": "m1", "stage": "connect", "intent": "next_steps"}


def _counting_handle(monkeypatch):
    calls = {"n": 0}

    def counting(req):
        calls["n"] += 1
        return real_handle(req)

    monkeypatch.setattr("app.api.main.handle", counting)
    return calls


def test_same_quick_action_is_miss_then_hit(client, set_env, monkeypatch):
    set_env(CACHE_ENABLED="true")
    calls = _counting_handle(monkeypatch)
    first = client.post(CHAT, json=QUICK_ACTION)
    second = client.post(CHAT, json=QUICK_ACTION)
    assert first.status_code == second.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert calls["n"] == 1, "a HIT must not call the orchestrator again"
    assert first.json() == second.json()


def test_free_text_request_is_never_cached(client, set_env, monkeypatch):
    set_env(CACHE_ENABLED="true")
    calls = _counting_handle(monkeypatch)
    body = {**QUICK_ACTION, "message": "What should I ask next?"}
    first = client.post(CHAT, json=body)
    second = client.post(CHAT, json=body)
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "MISS"
    assert calls["n"] == 2


def test_cache_disabled_always_reports_miss(client, set_env, monkeypatch):
    set_env(CACHE_ENABLED="false")
    calls = _counting_handle(monkeypatch)
    for _ in range(3):
        r = client.post(CHAT, json=QUICK_ACTION)
        assert r.status_code == 200
        assert r.headers["X-Cache"] == "MISS"
    assert calls["n"] == 3


def test_different_user_is_a_different_cache_entry(client, set_env, monkeypatch):
    set_env(CACHE_ENABLED="true")
    calls = _counting_handle(monkeypatch)
    first = client.post(CHAT, json={**QUICK_ACTION, "user_id": "alice"})
    second = client.post(CHAT, json={**QUICK_ACTION, "user_id": "bob"})
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "MISS"
    assert calls["n"] == 2


def test_different_topic_is_a_different_cache_entry(client, set_env, monkeypatch):
    set_env(CACHE_ENABLED="true")
    calls = _counting_handle(monkeypatch)
    client.post(CHAT, json={**QUICK_ACTION, "topic": "family"})
    client.post(CHAT, json={**QUICK_ACTION, "topic": "career"})
    assert calls["n"] == 2


def test_fallback_reply_is_not_cached(client, set_env, monkeypatch):
    set_env(USE_MOCK="false", LLM_API_KEY="dummy-key-for-tests", CACHE_ENABLED="true")

    def boom(_req):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(orchestrator, "handle_chat", boom, raising=False)
    first = client.post(CHAT, json=QUICK_ACTION)
    second = client.post(CHAT, json=QUICK_ACTION)
    assert first.status_code == second.status_code == 200
    assert first.json()["fallback_used"] is True
    assert second.json()["fallback_used"] is True
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "MISS"


def test_blocked_safety_reply_is_not_cached(client, set_env, monkeypatch):
    set_env(CACHE_ENABLED="true")
    calls = _counting_handle(monkeypatch)
    body = {**QUICK_ACTION, "message": "Will we get married?"}
    first = client.post(CHAT, json=body)
    second = client.post(CHAT, json=body)
    assert first.json()["safety"]["status"] == "blocked"
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "MISS"
    assert calls["n"] == 2


def test_error_responses_are_not_cached(client, set_env):
    set_env(CACHE_ENABLED="true")
    bad = {"user_id": "u", "match_id": "m", "stage": "nope"}
    for _ in range(2):
        r = client.post(CHAT, json=bad)
        assert r.status_code == 422
        assert "X-Cache" not in r.headers, "errors must never carry a cache header"
    good = client.post(CHAT, json=QUICK_ACTION)
    assert good.status_code == 200
    assert good.headers["X-Cache"] == "MISS", "an error must not have seeded the cache"


def test_cached_response_still_matches_the_frozen_schema(client, set_env):
    set_env(CACHE_ENABLED="true")
    client.post(CHAT, json=QUICK_ACTION)
    body = client.post(CHAT, json=QUICK_ACTION).json()
    assert set(body) == {"intent", "reply", "questions", "chips", "sources",
                         "safety", "fallback_used"}
    assert len(body["questions"]) <= 5
    assert len(body["chips"]) <= 4
    assert body["fallback_used"] is False

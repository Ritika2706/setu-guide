"""Day 2: rate limiting per user_id and per client IP."""
import pytest

CHAT = "/v1/guide/chat"
BASE = {"user_id": "u1", "match_id": "m1", "stage": "connect", "intent": "next_steps"}


def _post(client, headers=None, **overrides):
    return client.post(CHAT, json={**BASE, **overrides}, headers=headers)


def test_user_limit_returns_429_with_retry_after(client, set_env):
    set_env(RATE_LIMIT_PER_USER="3/minute", RATE_LIMIT_PER_IP="1000/minute")
    for _ in range(3):
        assert _post(client).status_code == 200
    r = _post(client)
    assert r.status_code == 429
    body = r.json()
    assert body["error"]["code"] == "rate_limited"
    assert body["error"]["details"] == []
    assert int(r.headers["Retry-After"]) >= 1


def test_other_users_keep_their_own_quota(client, set_env):
    set_env(RATE_LIMIT_PER_USER="2/minute", RATE_LIMIT_PER_IP="1000/minute")
    assert _post(client, user_id="a").status_code == 200
    assert _post(client, user_id="a").status_code == 200
    assert _post(client, user_id="a").status_code == 429
    assert _post(client, user_id="b").status_code == 200


def test_ip_limit_returns_429(client, set_env):
    set_env(RATE_LIMIT_PER_USER="1000/minute", RATE_LIMIT_PER_IP="2/minute")
    for _ in range(2):
        assert _post(client).status_code == 200
    assert _post(client).status_code == 429


def test_health_is_never_rate_limited(client, set_env):
    set_env(RATE_LIMIT_PER_USER="1/minute", RATE_LIMIT_PER_IP="1/minute")
    assert _post(client).status_code == 200
    assert _post(client).status_code == 429  # the chat route is now limited
    for _ in range(20):
        assert client.get("/health").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}


def test_forwarded_for_is_ignored_without_trusted_proxy(client, set_env):
    set_env(TRUSTED_PROXY="false", RATE_LIMIT_PER_USER="1000/minute", RATE_LIMIT_PER_IP="2/minute")
    assert _post(client, headers={"X-Forwarded-For": "9.9.9.9"}).status_code == 200
    assert _post(client, headers={"X-Forwarded-For": "8.8.8.8"}).status_code == 200
    # a forged header must not buy a fresh bucket: everything counts as one client
    assert _post(client, headers={"X-Forwarded-For": "7.7.7.7"}).status_code == 429


def test_forwarded_for_is_used_when_trusted(client, set_env):
    set_env(TRUSTED_PROXY="true", RATE_LIMIT_PER_USER="1000/minute", RATE_LIMIT_PER_IP="2/minute")
    for _ in range(2):
        assert _post(client, headers={"X-Forwarded-For": "9.9.9.9"}).status_code == 200
    assert _post(client, headers={"X-Forwarded-For": "9.9.9.9"}).status_code == 429
    assert _post(client, headers={"X-Forwarded-For": "8.8.8.8"}).status_code == 200


def test_429_body_and_header_are_stable(client, set_env):
    set_env(RATE_LIMIT_PER_USER="1/minute", RATE_LIMIT_PER_IP="1000/minute")
    _post(client)
    r = _post(client)
    assert set(r.json()) == {"error"}
    assert set(r.json()["error"]) == {"code", "message", "details"}
    assert r.json()["error"]["message"]
    assert r.headers["Retry-After"].isdigit()


def test_invalid_request_does_not_blow_up_the_limiter(client, set_env):
    set_env(RATE_LIMIT_PER_USER="1000/minute", RATE_LIMIT_PER_IP="1000/minute")
    bad = client.post(CHAT, json={"user_id": "u", "match_id": "m", "stage": "nope"})
    assert bad.status_code == 422
    assert _post(client).status_code == 200

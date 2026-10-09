"""Day 3: bad input and protocol failures must be a clean 4xx in the standard
error contract {"error": {"code", "message", "details"}} - never a 500, never
a stack trace, never an echo of what the caller sent.

Owner: DevOps 1 (app/api is ours; app/core, app/rag, app/safety are not).
"""
import json

import pytest

CHAT = "/v1/guide/chat"
# Canary value: if it ever comes back in an error body or a log line, we echo
# caller input where we must not.
ECHO = "ECHO-CANARY-VALUE"

BASE = {"user_id": "day3_bad_u1", "match_id": "day3_bad_m1",
        "stage": "connect", "intent": "next_steps"}


def assert_error_format(r, status, code):
    """Every failure body has exactly one key with code/message/details."""
    assert r.status_code == status, f"expected {status}, got {r.status_code}: {r.text[:200]}"
    assert r.headers["content-type"].startswith("application/json")
    assert r.headers.get("X-Request-Id"), "X-Request-Id missing on an error response"
    body = r.json()
    assert set(body) == {"error"}, f"unexpected top-level keys: {set(body)}"
    err = body["error"]
    assert set(err) == {"code", "message", "details"}, f"bad error keys: {set(err)}"
    assert err["code"] == code
    assert isinstance(err["message"], str) and err["message"]
    assert isinstance(err["details"], list)
    assert "Traceback" not in r.text
    assert ECHO not in r.text
    return err


# ------------------------------------------------- schema violations -> 422

_INVALID_JSON_PAYLOADS = [
    ("unknown stage", {**BASE, "stage": "teleport"}, "stage: enum"),
    ("unknown intent", {**BASE, "intent": "make_me_rich"}, "intent: enum"),
    ("missing user_id", {"match_id": BASE["match_id"], "stage": "connect",
                         "intent": "next_steps"}, "user_id: missing"),
    ("missing match_id", {"user_id": BASE["user_id"], "stage": "connect",
                          "intent": "next_steps"}, "match_id: missing"),
    ("neither intent nor message", {"user_id": BASE["user_id"],
                                    "match_id": BASE["match_id"],
                                    "stage": "connect"}, "value_error"),
    ("message over 500 chars", {**BASE, "message": ECHO * 30}, "message: string_too_long"),
    ("topic over 100 chars", {**BASE, "topic": ECHO * 6}, "topic: string_too_long"),
    ("wrong type: number user_id", {**BASE, "user_id": 12345}, "user_id: string_type"),
    ("wrong type: number match_id", {**BASE, "match_id": 999}, "match_id: string_type"),
    ("wrong type: number stage", {**BASE, "stage": 7}, "stage: enum"),
    ("wrong type: list intent", {**BASE, "intent": ["next_steps"]}, "intent: enum"),
    ("null values", {"user_id": None, "match_id": None, "stage": None,
                     "intent": None}, "user_id: string_type"),
]


@pytest.mark.parametrize("label,payload,expected_detail", _INVALID_JSON_PAYLOADS,
                         ids=[c[0] for c in _INVALID_JSON_PAYLOADS])
def test_schema_violations_are_422_invalid_request(client, label, payload, expected_detail):
    err = assert_error_format(client.post(CHAT, json=payload), 422, "invalid_request")
    assert expected_detail in err["details"], f"{label}: {err['details']}"


def test_empty_json_object_lists_every_missing_field(client):
    err = assert_error_format(client.post(CHAT, json={}), 422, "invalid_request")
    assert "user_id: missing" in err["details"]
    assert "match_id: missing" in err["details"]


# -------------------------------------------------- malformed / raw bodies

def test_empty_body(client):
    r = client.post(CHAT, content=b"", headers={"content-type": "application/json"})
    assert_error_format(r, 422, "invalid_request")


def test_malformed_json_body(client):
    r = client.post(CHAT, content='{"user_id": ' + ECHO,
                    headers={"content-type": "application/json"})
    assert_error_format(r, 422, "invalid_request")


def test_wrong_content_type(client):
    r = client.post(CHAT, content=json.dumps(BASE), headers={"content-type": "text/plain"})
    assert_error_format(r, 422, "invalid_request")


def test_very_large_body_is_rejected_cleanly(client):
    """~1 MB of message text: 422, not 413/500, and no echo of the payload."""
    r = client.post(CHAT, json={**BASE, "message": ECHO + "x" * 1_000_000})
    assert_error_format(r, 422, "invalid_request")
    assert "message: string_too_long" in r.json()["error"]["details"]


# ----------------------------------------------------------- routes / verbs

def test_unknown_route_is_404(client):
    assert_error_format(client.get("/nope/such/path"), 404, "not_found")


def test_unknown_route_post_is_404(client):
    assert_error_format(client.post("/v1/guide/unknown", json=BASE), 404, "not_found")


def test_wrong_method_on_chat_is_405(client):
    assert_error_format(client.get(CHAT), 405, "method_not_allowed")
    assert_error_format(client.delete(CHAT), 405, "method_not_allowed")


# ------------------------------------------------------- unicode / free text

_UNICODE_CASES = [
    ("hindi message", {"message": "नमस्ते! मुझे इस रिश्ते में आगे क्या करना चाहिए? सलाह दो।"}),
    ("emoji only", {"message": "\U0001f600\U0001f496\U0001f680"}),
    ("mixed unicode topic", {"intent": "next_steps", "topic": "क्या यह सही है? 🚀"}),
    ("rtl text", {"message": "مرحبا، كيف أتواصل معها؟"}),
    ("zero width + accents", {"message": "h\u200b\u00e9llo w\u0302rld \u0141\u00d8D\u0110"}),
]


@pytest.mark.parametrize("label,extra", _UNICODE_CASES, ids=[c[0] for c in _UNICODE_CASES])
def test_unicode_input_returns_200_without_crash(client, label, extra):
    payload = {"user_id": "day3_uni_u1", "match_id": "day3_uni_m1",
               "stage": "understand", **extra}
    r = client.post(CHAT, json=payload)
    assert r.status_code == 200, f"{label}: {r.status_code} {r.text[:200]}"
    body = r.json()
    assert isinstance(body["reply"], str) and body["reply"]
    assert body["safety"]["status"] in ("pass", "modified", "blocked")
    assert isinstance(body["fallback_used"], bool)


def test_message_with_newlines_and_tabs_is_accepted(client):
    payload = {"user_id": "day3_uni_u2", "match_id": "day3_uni_m2",
               "stage": "discuss", "message": "line one\nline two\tend 🙂"}
    assert client.post(CHAT, json=payload).status_code == 200

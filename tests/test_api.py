"""Day 1 contract tests for POST /v1/guide/chat, /health and the error format.

Covers the Day 1 acceptance list: happy paths (intent, message-only, all
8 stages x 4 intents), every 422 case, the 404/429/500 formats, and the rule
that no caller text is echoed back in an error.
"""
from typing import Dict, List

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.main import app
from app.schemas.guide import GuideResponse, Intent, Stage

STAGES: List[str] = [s.value for s in Stage]
INTENTS: List[str] = [i.value for i in Intent]
BASE: Dict[str, str] = {"user_id": "u1", "match_id": "m1"}
# A value that must never come back to the caller in an error or a log line.
SENTINEL = "ZzLeakCantEcho9f3a"


def post(client: TestClient, **fields):
    return client.post("/v1/guide/chat", json={**BASE, **fields})


def assert_error_format(body: dict, code: str):
    assert set(body) == {"error"}, body
    assert set(body["error"]) == {"code", "message", "details"}, body["error"]
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    assert isinstance(body["error"]["details"], list)


# ---------------------------------------------------------------- happy paths

def test_intent_request_returns_200(client):
    r = post(client, stage="connect", intent="next_steps")
    assert r.status_code == 200
    parsed = GuideResponse.model_validate(r.json())  # frozen response schema
    assert parsed.intent is Intent.next_steps
    assert parsed.safety.status.value == "pass"
    assert parsed.safety.flags == []
    assert parsed.fallback_used is False
    assert isinstance(parsed.reply, str) and parsed.reply
    assert len(parsed.questions) <= 5
    assert len(parsed.chips) <= 4
    assert all(isinstance(s, str) for s in parsed.sources)


def test_message_only_returns_200_with_default_intent(client):
    r = post(client, stage="understand", message="What are some good questions to ask?")
    assert r.status_code == 200
    body = r.json()
    # intent missing in the request -> a default intent comes back in the response
    assert body["intent"] in INTENTS
    assert set(body) == {"intent", "reply", "questions", "chips", "sources",
                         "safety", "fallback_used"}


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("intent", INTENTS)
def test_all_stages_and_intents(client, stage, intent):
    assert post(client, stage=stage, intent=intent).status_code == 200


def test_mock_reply_is_hardcoded(client):
    r = post(client, stage="reflect", message=f"Any conversation ideas {SENTINEL}?")
    assert r.status_code == 200
    assert SENTINEL not in r.text


# ------------------------------------------------------------------ 422 cases

def test_unknown_stage_422(client):
    r = post(client, stage="no_such_stage", intent="next_steps")
    assert r.status_code == 422
    assert_error_format(r.json(), "invalid_request")


def test_unknown_intent_422(client):
    r = post(client, stage="connect", intent="make_my_decisions")
    assert r.status_code == 422
    assert_error_format(r.json(), "invalid_request")


def test_neither_intent_nor_message_422(client):
    r = post(client, stage="connect")
    assert r.status_code == 422
    assert_error_format(r.json(), "invalid_request")


def test_message_over_500_chars_422(client):
    r = post(client, stage="connect", intent="next_steps", message="a" * 501)
    assert r.status_code == 422
    assert_error_format(r.json(), "invalid_request")


def test_message_exactly_500_chars_ok(client):
    assert post(client, stage="connect", message="a" * 500).status_code == 200


def test_topic_over_100_chars_422(client):
    r = post(client, stage="connect", intent="next_steps", topic="t" * 101)
    assert r.status_code == 422
    assert_error_format(r.json(), "invalid_request")


def test_topic_exactly_100_chars_ok(client):
    assert post(client, stage="connect", intent="next_steps", topic="t" * 100).status_code == 200


@pytest.mark.parametrize("missing", ["user_id", "match_id", "stage"])
def test_missing_required_field_422(client, missing):
    body = {"stage": "connect", "intent": "next_steps", **BASE}
    del body[missing]
    r = client.post("/v1/guide/chat", json=body)
    assert r.status_code == 422
    assert_error_format(r.json(), "invalid_request")


# ------------------------------------------------------- no user input echoed

@pytest.mark.parametrize(
    "fields",
    [
        {"stage": "connect", "intent": "next_steps", "message": SENTINEL * 40},  # too long
        {"stage": SENTINEL, "intent": "next_steps"},                              # unknown stage
        {"stage": "connect", "intent": SENTINEL},                                 # unknown intent
        {"stage": "connect", "intent": "next_steps", "topic": SENTINEL * 10},     # too long topic
        {"stage": SENTINEL},                                                       # unknown stage + missing fields
    ],
)
def test_422_does_not_echo_input(client, fields):
    r = post(client, **fields)
    assert r.status_code == 422
    assert SENTINEL not in r.text
    assert_error_format(r.json(), "invalid_request")


def test_unknown_route_404_same_format(client):
    r = client.get("/v1/guide/does-not-exist")
    assert r.status_code == 404
    assert_error_format(r.json(), "not_found")


def test_wrong_method_405_same_format(client):
    r = client.get("/v1/guide/chat")
    assert r.status_code == 405
    assert_error_format(r.json(), "method_not_allowed")


def test_rate_limited_format(client, monkeypatch):
    """429 format only for now; actual rate limiting lands on Day 2."""
    def _limited(_req):
        raise HTTPException(status_code=429, detail=f"slow down {SENTINEL}")

    monkeypatch.setattr("app.api.main.handle", _limited)
    r = post(client, stage="connect", intent="next_steps")
    assert r.status_code == 429
    assert_error_format(r.json(), "rate_limited")
    assert SENTINEL not in r.text


def test_internal_error_format(client_no_raise, monkeypatch):
    def _boom(_req):
        raise RuntimeError(f"exploded with {SENTINEL}")

    monkeypatch.setattr("app.api.main.handle", _boom)
    r = post(client_no_raise, stage="connect", intent="next_steps")
    assert r.status_code == 500
    assert_error_format(r.json(), "internal_error")
    assert SENTINEL not in r.text


# --------------------------------------------------------------------- health

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_swagger_docs_available(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200

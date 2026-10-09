"""Day 3: whatever path a request takes (success, validation error, rate
limit, unknown route, internal crash), the logs must never contain the
message text, the topic, user_id, match_id or the API key.

One test drives every path so "no leak" cannot be an accident of a path that
simply did not run.
"""
import json
import logging

CHAT = "/v1/guide/chat"

MARKER_MESSAGE = "PRIVACY-MARKER-MESSAGE private thoughts about my match"
MARKER_TOPIC = "PRIVACY-MARKER-TOPIC"
MARKER_USER = "privacy-marker-user-77"
MARKER_MATCH = "privacy-marker-match-77"
MARKER_API_KEY = "sk-PRIVACY-MARKER-API-KEY-88"
MARKER_INTERNAL = "PRIVACY-MARKER-INTERNAL-99"

ALL_MARKERS = [MARKER_MESSAGE, MARKER_TOPIC, MARKER_USER, MARKER_MATCH,
               MARKER_API_KEY, MARKER_INTERNAL]


def _request_markers():
    return {"user_id": MARKER_USER, "match_id": MARKER_MATCH,
            "stage": "family", "message": MARKER_MESSAGE, "topic": MARKER_TOPIC}


def test_no_private_data_in_logs_from_any_path(client, client_no_raise, set_env,
                                                monkeypatch, caplog):
    set_env(USE_MOCK="true", LLM_API_KEY=MARKER_API_KEY,
            RATE_LIMIT_PER_USER="1/minute", RATE_LIMIT_PER_IP="1000/minute",
            LOG_LEVEL="INFO")

    with caplog.at_level(logging.INFO, logger="setu.guide"):
        ok = client.post(CHAT, json=_request_markers())                       # 200
        bad = client.post(CHAT, json={"user_id": MARKER_USER,
                                      "match_id": MARKER_MATCH, "stage": "connect",
                                      "topic": MARKER_TOPIC + "x" * 100})     # 422
        client.get("/does-not-exist")                                          # 404
        limited = client.post(CHAT, json=_request_markers())                   # 429 (1/min used)
        assert ok.status_code == 200
        assert bad.status_code == 422
        assert limited.status_code == 429

        # The user bucket is spent, so lift it - otherwise the crash request
        # below would be stopped at the limiter and never reach the 500 path.
        set_env(RATE_LIMIT_PER_USER="1000/minute")

        def crash(_req):
            raise ValueError(MARKER_INTERNAL)

        monkeypatch.setattr("app.api.main.handle", crash)
        client_no_raise.post(CHAT, json=_request_markers())                    # 500

    # Guard against the test silently passing because nothing was logged.
    access_lines = [r.getMessage() for r in caplog.records
                    if r.getMessage().startswith("http_request ")]
    statuses = {json.loads(line.split("http_request ", 1)[1])["status"]
                for line in access_lines}
    assert {200, 422, 404, 429, 500} <= statuses, f"missing paths in log: {statuses}"

    logged = caplog.text
    for marker in ALL_MARKERS:
        assert marker not in logged, f"marker leaked into logs: {marker}"
    # rate-limit log names the scope only, never the id behind the bucket
    assert "rate_limited scope=user" in logged


def test_response_bodies_never_carry_the_api_key(client, set_env):
    set_env(USE_MOCK="true", LLM_API_KEY=MARKER_API_KEY)
    ok = client.post(CHAT, json=_request_markers())
    bad = client.post(CHAT, json={"user_id": MARKER_USER, "match_id": MARKER_MATCH,
                                  "stage": "nope", "message": MARKER_MESSAGE})
    for r in (ok, bad):
        assert MARKER_API_KEY not in r.text
        assert MARKER_USER not in r.text

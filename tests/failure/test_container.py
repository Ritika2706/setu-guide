"""Day 3: container-level failure tests. Docker required.

They skip themselves when the daemon is not running or the image is missing:
    docker build -t setu-guide-api:day3 -f docker/Dockerfile .
Override with SETU_TEST_IMAGE / SETU_TEST_PORT / DOCKER_EXE if needed.

Covered here (things a TestClient cannot prove):
- missing secret with USE_MOCK=false -> container fails fast with one clear line
- docker restart under load          -> service returns and HEALTHCHECK says healthy
- container logs                     -> no message text, topic, ids or API key
"""
import functools
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request

import pytest

IMAGE = os.environ.get("SETU_TEST_IMAGE", "setu-guide-api:day3")
PORT = int(os.environ.get("SETU_TEST_PORT", "8010"))
CONTAINER = "setu-day3-failure"
BASE_URL = f"http://127.0.0.1:{PORT}"
CHAT = "/v1/guide/chat"

MARKER_MESSAGE = "PRIVACY-MARKER-CONTAINER-MSG about my match"
MARKER_TOPIC = "PRIVACY-MARKER-CONTAINER-TOPIC"
MARKER_USER = "privacy-container-user"
MARKER_MATCH = "privacy-container-match"
MARKER_API_KEY = "sk-PRIVACY-CONTAINER-KEY"


@functools.lru_cache(maxsize=1)
def _docker_exe():
    """Docker Desktop's own binary first: a stray shim can shadow PATH."""
    candidates = [os.environ.get("DOCKER_EXE"),
                  r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
                  shutil.which("docker")]
    for cand in dict.fromkeys(c for c in candidates if c):
        try:
            p = subprocess.run([cand, "version", "--format", "{{.Server.Version}}"],
                               capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if p.returncode == 0:
            return cand
    return None


@functools.lru_cache(maxsize=1)
def _image_exists():
    exe = _docker_exe()
    if not exe:
        return False
    try:
        return subprocess.run([exe, "image", "inspect", IMAGE],
                              capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(
    not _image_exists(),
    reason=f"docker unavailable or image {IMAGE!r} not built (see tests/README.md)",
)


def _docker(*args, timeout=180):
    exe = _docker_exe()
    assert exe, "docker executable not found"
    return subprocess.run([exe, *args], capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")


def _wait_http(path, timeout=60):
    """Poll until the endpoint answers 200; raise with the last error."""
    deadline = time.monotonic() + timeout
    last = "never attempted"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(BASE_URL + path, timeout=3) as resp:
                if resp.status == 200:
                    return 200
                last = f"HTTP {resp.status}"
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            last = type(exc).__name__
        time.sleep(0.5)
    raise AssertionError(f"{path} not answering 200 after {timeout}s (last: {last})")


def _wait_docker_health(timeout=150):
    """Poll the container HEALTHCHECK (interval 30s, start period 15s)."""
    deadline = time.monotonic() + timeout
    status = "unknown"
    while time.monotonic() < deadline:
        p = _docker("inspect", "-f", "{{.State.Health.Status}}", CONTAINER, timeout=30)
        status = (p.stdout or "").strip() or "unknown"
        if status in ("healthy", "unhealthy"):
            return status
        time.sleep(2)
    return status


def _post_chat(payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE_URL + CHAT, data=data, method="POST",
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status


@pytest.fixture
def running_container():
    _docker("rm", "-f", CONTAINER)
    p = _docker("run", "-d", "--name", CONTAINER, "-p", f"{PORT}:8000",
                "-e", "USE_MOCK=true",
                "-e", f"LLM_API_KEY={MARKER_API_KEY}",
                "-e", "RATE_LIMIT_PER_USER=100000/minute",
                "-e", "RATE_LIMIT_PER_IP=100000/minute", IMAGE)
    assert p.returncode == 0, f"could not start container: {p.stderr}"
    try:
        yield
    finally:
        _docker("rm", "-f", CONTAINER)


# --------------------------------------------------------------------- tests

def test_container_fails_fast_without_secret():
    """USE_MOCK=false and no LLM_API_KEY: process must exit non-zero with the
    configuration message, not start and fail on the first request."""
    p = _docker("run", "--rm", "-e", "USE_MOCK=false", "-e", "LLM_API_KEY=", IMAGE)
    out = (p.stdout or "") + (p.stderr or "")
    assert p.returncode != 0, "container started without LLM_API_KEY"
    assert "LLM_API_KEY is required when USE_MOCK=false" in out, out[-800:]
    # the value (there is none) and unrelated internals stay out of the message
    assert "Traceback" in out, "expected a startup traceback on stderr"


def test_container_recovers_after_restart_under_load(running_container):
    _wait_http("/health", 60)

    stop = threading.Event()
    counts = {"chat_200": 0, "health_200": 0, "server_error": 0,
              "rate_limited": 0, "connection": 0}

    def load():
        n = 0
        while not stop.is_set():
            n += 1
            try:
                if n % 2:
                    status = _post_chat({"user_id": f"restart_u{n % 7}",
                                         "match_id": "restart_m1",
                                         "stage": "agree", "intent": "next_steps"})
                    counts["chat_200" if status == 200 else "server_error"] += 1
                else:
                    with urllib.request.urlopen(BASE_URL + "/health", timeout=3) as resp:
                        counts["health_200" if resp.status == 200 else "server_error"] += 1
            except urllib.error.HTTPError as exc:
                counts["rate_limited" if exc.code == 429 else "server_error"] += 1
            except (urllib.error.URLError, ConnectionError, OSError):
                counts["connection"] += 1  # expected while the container bounces
            time.sleep(0.1)

    threads = [threading.Thread(target=load, daemon=True) for _ in range(5)]
    for t in threads:
        t.start()
    try:
        time.sleep(3)                      # steady load first
        p = _docker("restart", CONTAINER, timeout=120)
        assert p.returncode == 0, p.stderr
        time.sleep(5)                      # keep loading across the bounce
        _wait_http("/health", 90)          # HTTP is back
        health = _wait_docker_health(150)  # and the HEALTHCHECK agrees
    finally:
        stop.set()
        for t in threads:
            t.join(timeout=10)

    assert health == "healthy", f"HEALTHCHECK did not recover: {health}"
    assert counts["chat_200"] > 10 and counts["health_200"] > 10, counts
    assert counts["server_error"] == 0, f"service answered errors under load: {counts}"
    assert counts["rate_limited"] == 0, f"unexpected 429 under load: {counts}"
    # Final outside check once everything settled.
    assert _wait_http("/health", 10) == 200


def test_container_logs_carry_no_private_data(running_container):
    _wait_http("/health", 60)
    assert _post_chat({"user_id": MARKER_USER, "match_id": MARKER_MATCH,
                       "stage": "family", "message": MARKER_MESSAGE,
                       "topic": MARKER_TOPIC}) == 200
    # schema violation carrying the same markers -> error path
    data = json.dumps({"user_id": MARKER_USER, "match_id": MARKER_MATCH,
                       "stage": "not-a-stage", "message": MARKER_MESSAGE}).encode()
    req = urllib.request.Request(BASE_URL + CHAT, data=data, method="POST",
                                 headers={"content-type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError:
        pass
    time.sleep(1)

    p = _docker("logs", CONTAINER, timeout=60)
    text = (p.stdout or "") + (p.stderr or "")
    assert "http_request" in text, "no structured access logs found in container output"
    for marker in (MARKER_MESSAGE, MARKER_TOPIC, MARKER_USER, MARKER_MATCH, MARKER_API_KEY):
        assert marker not in text, f"container log leaked {marker}"

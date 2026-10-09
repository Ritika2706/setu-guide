"""Scenario C - rate limit behaviour (Day 3 load tests).

    locust -f tests/load/scenario_c.py --headless -u 6 -r 1 -t 90s \\
        --csv tests/load/results/c_ratelimit

Container for this run (user limit back at the default, only the IP limit
raised so the shared test machine IP cannot block the innocent users):

    docker run -d --name setu-day3-load -p 8000:8000 -e USE_MOCK=true \\
      -e RATE_LIMIT_PER_USER=30/minute -e RATE_LIMIT_PER_IP=100000/minute \\
      setu-guide-api:day3

AbusiveUser: every instance writes the SAME user_id (load_abusive_user) and
sends ~5 req/s, far above 30/minute, so that id must collect 429s with a
Retry-After header. NormalUser: one fresh user_id each, one request every
3-6 s (max 20/min), so ANY 429 in C:other-users-* means the per-user limit
leaked across users.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from locust import between, constant_pacing, task  # noqa: E402

from common import SetuUser  # noqa: E402


class AbusiveUser(SetuUser):
    # 5 req/s against the 30/minute per-user placeholder limit.
    wait_time = constant_pacing(0.2)

    def on_start(self):
        super().on_start()
        # ONE id for the whole run - this is the user that must get 429s.
        self.user_id = "load_abusive_user"

    @task
    def hammer(self):
        with self.client.post("/v1/guide/chat",
                              json=self.payload_quick_action("connect", "next_steps"),
                              catch_response=True) as resp:
            resp.request_meta["name"] = "C:abusive-status-%d" % resp.status_code


class NormalUser(SetuUser):
    # 3-6 s between calls = max 20/min, comfortably under 30/minute.
    wait_time = between(3.0, 6.0)

    @task
    def quick_action(self):
        with self.client.post("/v1/guide/chat", json=self.payload_quick_action(),
                              catch_response=True) as resp:
            resp.request_meta["name"] = "C:other-users-status-%d" % resp.status_code

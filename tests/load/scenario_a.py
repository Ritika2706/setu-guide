"""Scenario A - mixed traffic (Day 3 load tests).

    locust -f tests/load/scenario_a.py --headless -u 20 -r 0.67 -t 5m \\
        --csv tests/load/results/a_mixed

70% quick-action requests (intent set, no message) and 30% free-text
messages, random stage and intent, one synthetic session per virtual user.
Run with USE_MOCK=true and the rate limits raised for the run (see
tests/README.md) so the limiter does not distort the latency numbers.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from locust import between, task  # noqa: E402

from common import SetuUser  # noqa: E402


class MixedTrafficUser(SetuUser):
    wait_time = between(0.5, 1.5)

    @task(70)
    def quick_action(self):
        self.client.post("/v1/guide/chat", json=self.payload_quick_action(),
                         name="A:quick-action")

    @task(30)
    def free_text_message(self):
        self.client.post("/v1/guide/chat", json=self.payload_free_text(),
                         name="A:free-text")

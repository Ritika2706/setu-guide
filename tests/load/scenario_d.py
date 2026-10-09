"""Scenario D - /health under load (Day 3 load tests).

    locust -f tests/load/scenario_d.py --headless -u 20 -r 0.67 -t 60s \\
        --csv tests/load/results/d_health

Run this against a container with the DEFAULT rate limits (30/minute per
user, 60/minute per IP): ~60 req/s of /health from one machine IP would be
rate limited within seconds if the endpoint were not exempt, so any 429 here
is a failure. /health must also stay fast (p95 well under 2 s).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from locust import between, task  # noqa: E402

from common import SetuUser  # noqa: E402


class HealthUser(SetuUser):
    wait_time = between(0.1, 0.4)

    @task
    def health(self):
        self.client.get("/health", name="D:health")

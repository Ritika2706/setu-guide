"""Scenario B - cache effect (Day 3 load tests).

    locust -f tests/load/scenario_b.py --headless -u 20 -r 4 -t 60s \\
        --csv tests/load/results/b_cache

Each virtual user repeats a few fixed quick actions: the first pass fills the
cache (X-Cache: MISS) and every later pass of the same key is a HIT. The
request name is rewritten from the X-Cache header, so locust reports the MISS
and HIT latency distributions separately (B:MISS vs B:HIT).
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from locust import between, task  # noqa: E402

from common import INTENTS, STAGES, SetuUser  # noqa: E402


class CacheEffectUser(SetuUser):
    # Fast repeats: the point is HIT vs MISS, not think time.
    wait_time = between(0.1, 0.3)

    def on_start(self):
        super().on_start()
        # A few fixed quick actions per user: the first pass fills the cache
        # (MISS), every later pass of the same key is a HIT.
        self.cycle = [(random.choice(STAGES), random.choice(INTENTS))
                      for _ in range(3)]
        self.i = 0

    @task
    def repeat_quick_action(self):
        stage, intent = self.cycle[self.i % len(self.cycle)]
        self.i += 1
        with self.client.post("/v1/guide/chat",
                              json=self.payload_quick_action(stage, intent),
                              catch_response=True) as resp:
            if resp.status_code == 200:
                resp.request_meta["name"] = "B:%s" % resp.headers.get("X-Cache", "unknown")
            else:
                resp.request_meta["name"] = "B:status-%d" % resp.status_code

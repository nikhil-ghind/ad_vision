"""Kafka consumer: aggregate impression/click events, compute CTR."""
from __future__ import annotations
import json
import threading
from collections import defaultdict
from kafka import KafkaConsumer
from typing import Dict, Callable


class AdMetricsConsumer:
    def __init__(self, bootstrap_servers: str = "localhost:9092",
                 group_id: str = "ad_metrics"):
        self.impressions: Dict[str, int] = defaultdict(int)
        self.clicks:      Dict[str, int] = defaultdict(int)
        self._consumer = KafkaConsumer(
            "ad_impressions", "ad_clicks",
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest",
        )
        self._running = False

    def _process(self, record):
        event = record.value
        cid = event.get("campaign_id", "unknown")
        if event.get("event_type") == "impression":
            self.impressions[cid] += 1
        elif event.get("event_type") == "click":
            self.clicks[cid] += 1

    def start(self, callback: Callable[[str, int, int, float], None] = None):
        self._running = True
        def _run():
            for record in self._consumer:
                if not self._running:
                    break
                self._process(record)
                if callback:
                    cid = record.value.get("campaign_id", "")
                    imp = self.impressions[cid]
                    clk = self.clicks[cid]
                    ctr = clk / imp if imp > 0 else 0.0
                    callback(cid, imp, clk, ctr)
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t

    def stop(self):
        self._running = False
        self._consumer.close()

    def get_ctr(self, campaign_id: str) -> float:
        imp = self.impressions[campaign_id]
        return self.clicks[campaign_id] / imp if imp > 0 else 0.0

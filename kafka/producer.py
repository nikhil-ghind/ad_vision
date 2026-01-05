"""Kafka producer: emit ad impression and click events."""
from __future__ import annotations
import json
import time
from typing import Dict, Any
from kafka import KafkaProducer


class AdEventProducer:
    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            retries=3,
        )

    def emit_impression(self, user_id: str, campaign_id: str,
                         clearing_price: float, extra: Dict = None):
        event = {
            "event_type": "impression",
            "user_id": user_id,
            "campaign_id": campaign_id,
            "clearing_price_cpm": clearing_price,
            "ts": int(time.time() * 1000),
            **(extra or {}),
        }
        self.producer.send("ad_impressions", event)

    def emit_click(self, user_id: str, campaign_id: str, extra: Dict = None):
        event = {
            "event_type": "click",
            "user_id": user_id,
            "campaign_id": campaign_id,
            "ts": int(time.time() * 1000),
            **(extra or {}),
        }
        self.producer.send("ad_clicks", event)

    def flush(self):
        self.producer.flush()

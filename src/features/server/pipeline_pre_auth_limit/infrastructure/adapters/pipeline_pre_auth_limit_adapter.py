"""
Blueprint:
- Thread-safe memory token bucket adapter reading thresholds from external component config.yml.
"""
import os
import time
import yaml  # type: ignore[import-untyped]
import threading
from typing import Dict, Tuple, Optional
from src.features.server.pipeline_pre_auth_limit.infrastructure.ports.pipeline_pre_auth_limit_port import PreAuthRateLimitPort

class InMemoryPreAuthRateLimitAdapter(PreAuthRateLimitPort):
    def __init__(self, config_path: Optional[str] = None) -> None:
        self._buckets: Dict[str, Tuple[float, float]] = {}
        self._lock = threading.Lock()
        path = config_path or os.path.join(os.path.dirname(__file__), "../../config.yml")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
            self.default_tokens = data.get("max_tokens", 100)
            self.default_refill = float(data.get("refill_rate_per_sec", 10.0))
        else:
            self.default_tokens = 100
            self.default_refill = 10.0

    def consume(self, client_ip: str, tokens: int, refill_rate: float, cost: float = 1.0) -> bool:
        with self._lock:
            now = time.monotonic()
            effective_tokens = tokens if tokens > 0 else self.default_tokens
            effective_refill = refill_rate if refill_rate > 0.0 else self.default_refill
            if client_ip not in self._buckets:
                self._buckets[client_ip] = (float(effective_tokens) - cost, now)
                return True
            curr_tokens, last_time = self._buckets[client_ip]
            elapsed = now - last_time
            curr_tokens = min(float(effective_tokens), curr_tokens + (elapsed * effective_refill))
            if curr_tokens >= cost:
                self._buckets[client_ip] = (curr_tokens - cost, now)
                return True
            self._buckets[client_ip] = (curr_tokens, now)
            return False

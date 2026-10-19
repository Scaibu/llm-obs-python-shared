import os
import time
import yaml  # type: ignore[import-untyped]
import threading
from collections import OrderedDict
from typing import Dict, Tuple, Optional
from src.features.server.pipeline_pre_auth_limit.infrastructure.ports.pipeline_pre_auth_limit_port import PreAuthRateLimitPort

class InMemoryPreAuthRateLimitAdapter(PreAuthRateLimitPort):
    def __init__(self, config_path: Optional[str] = None, max_entries: int = 10000, idle_ttl_seconds: float = 3600.0) -> None:
        self._buckets: OrderedDict[str, Tuple[float, float]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_entries = max_entries
        self._idle_ttl_seconds = idle_ttl_seconds
        path = config_path or os.path.join(os.path.dirname(__file__), "../../config.yml")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
            self.default_tokens = data.get("max_tokens", 100)
            self.default_refill = float(data.get("refill_rate_per_sec", 10.0))
        else:
            self.default_tokens = 100
            self.default_refill = 10.0

    def _evict_stale_locked(self, now: float) -> None:
        stale_threshold = now - self._idle_ttl_seconds
        keys_to_remove = []
        for k, (_, last_time) in self._buckets.items():
            if last_time < stale_threshold:
                keys_to_remove.append(k)
            else:
                break
        for k in keys_to_remove:
            del self._buckets[k]

        while len(self._buckets) >= self._max_entries:
            self._buckets.popitem(last=False)

    def consume(self, client_ip: str, tokens: int, refill_rate: float, cost: float = 1.0) -> bool:
        with self._lock:
            now = time.monotonic()
            effective_tokens = tokens if tokens > 0 else self.default_tokens
            effective_refill = refill_rate if refill_rate > 0.0 else self.default_refill

            self._evict_stale_locked(now)

            if client_ip not in self._buckets:
                self._buckets[client_ip] = (float(effective_tokens) - cost, now)
                self._buckets.move_to_end(client_ip)
                return True

            curr_tokens, last_time = self._buckets[client_ip]
            elapsed = max(0.0, now - last_time)
            curr_tokens = min(float(effective_tokens), curr_tokens + (elapsed * effective_refill))

            if curr_tokens >= cost:
                self._buckets[client_ip] = (curr_tokens - cost, now)
                self._buckets.move_to_end(client_ip)
                return True

            self._buckets[client_ip] = (curr_tokens, now)
            self._buckets.move_to_end(client_ip)
            return False

import time
from typing import Any, Dict, Optional
from src.features.server.pipeline_tenant_quota.infrastructure.ports.pipeline_tenant_quota_port import (
    TenantQuotaPort,
)


class DistributedRedisTenantQuotaAdapter(TenantQuotaPort):
    def __init__(self, redis_client: Optional[Any] = None) -> None:
        self._redis = redis_client
        self._fallback_buckets: Dict[str, Dict[str, float]] = {}

    def consume_tenant_quota(
        self,
        tenant_id: str,
        tokens: int,
        refill_rate: float,
        cost: float = 1.0,
    ) -> bool:
        if self._redis is not None:
            try:
                pass
            except Exception:
                pass
        now = time.monotonic()
        bucket = self._fallback_buckets.setdefault(tenant_id, {"tokens": float(tokens), "last_refill": now})
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(float(tokens), bucket["tokens"] + elapsed * refill_rate)
        bucket["last_refill"] = now

        if bucket["tokens"] >= cost:
            bucket["tokens"] -= cost
            return True
        return False

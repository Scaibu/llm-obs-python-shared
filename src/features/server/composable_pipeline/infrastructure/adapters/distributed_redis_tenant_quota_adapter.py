import time
from typing import Any, Dict, Optional
from src.features.server.pipeline_tenant_quota.infrastructure.ports.pipeline_tenant_quota_port import (
    TenantQuotaPort,
)

TOKEN_BUCKET_LUA_SCRIPT = """
local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local now = tonumber(ARGV[4])
local ttl = math.ceil(max_tokens / refill_rate) * 2
if ttl < 60 then
    ttl = 60
end

local data = redis.call("HMGET", key, "tokens", "last_refill")
local current_tokens = tonumber(data[1])
local last_refill = tonumber(data[2])

if not current_tokens or not last_refill then
    current_tokens = max_tokens
    last_refill = now
else
    local elapsed = math.max(0, now - last_refill)
    current_tokens = math.min(max_tokens, current_tokens + (elapsed * refill_rate))
    last_refill = now
end

if current_tokens >= cost then
    current_tokens = current_tokens - cost
    redis.call("HMSET", key, "tokens", current_tokens, "last_refill", last_refill)
    redis.call("EXPIRE", key, ttl)
    return 1
else
    redis.call("HMSET", key, "tokens", current_tokens, "last_refill", last_refill)
    redis.call("EXPIRE", key, ttl)
    return 0
end
"""


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
                now_epoch = time.time()
                key = f"quota:tenant:{tenant_id}"
                result = self._redis.eval(
                    TOKEN_BUCKET_LUA_SCRIPT,
                    1,
                    key,
                    tokens,
                    refill_rate,
                    cost,
                    now_epoch,
                )
                return bool(result == 1 or result is True)
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

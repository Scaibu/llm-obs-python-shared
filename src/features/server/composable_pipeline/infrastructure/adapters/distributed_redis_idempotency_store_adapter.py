from typing import Any, Dict, Optional, Tuple
from src.features.server.composable_pipeline.infrastructure.ports.idempotency_store_port import (
    IdempotencyStorePort,
)


class DistributedRedisIdempotencyStoreAdapter(IdempotencyStorePort):
    def __init__(self, redis_client: Optional[Any] = None) -> None:
        self._redis = redis_client
        self._fallback_store: Dict[str, Tuple[str, Optional[Tuple[int, bytes]]]] = {}

    async def try_acquire(self, key: str, ttl_seconds: int = 86400) -> bool:
        if self._redis is not None:
            try:
                res = await self._redis.set(f"idemp:{key}", "in_flight", nx=True, ex=ttl_seconds)
                return bool(res)
            except Exception:
                pass
        if key in self._fallback_store:
            return False
        self._fallback_store[key] = ("in_flight", None)
        return True

    async def record_response(self, key: str, status_code: int, response_body: bytes) -> None:
        if self._redis is not None:
            try:
                await self._redis.set(f"idemp:resp:{key}", f"{status_code}".encode() + b"::" + response_body)
                return
            except Exception:
                pass
        self._fallback_store[key] = ("completed", (status_code, response_body))

    async def get_response(self, key: str) -> Optional[Tuple[int, bytes]]:
        if self._redis is not None:
            try:
                raw = await self._redis.get(f"idemp:resp:{key}")
                if raw:
                    parts = raw.split(b"::", 1)
                    return int(parts[0].decode()), parts[1]
            except Exception:
                pass
        entry = self._fallback_store.get(key)
        if entry and entry[0] == "completed":
            return entry[1]
        return None

"""
Blueprint:
- In-memory idempotency store adapter tracking locks and completed responses with TTL expiration.
"""
import time
from typing import Dict, Optional, Tuple
from src.features.server.composable_pipeline.infrastructure.ports.idempotency_store_port import (
    IdempotencyStorePort,
)


class InMemoryIdempotencyStoreAdapter(IdempotencyStorePort):
    def __init__(self) -> None:
        self._locks: Dict[str, float] = {}
        self._responses: Dict[str, Tuple[int, bytes, float]] = {}

    async def try_acquire(self, key: str, ttl_seconds: int = 86400) -> bool:
        now = time.monotonic()
        if key in self._locks:
            expiry = self._locks[key]
            if now < expiry:
                return False
        self._locks[key] = now + ttl_seconds
        return True

    async def record_response(self, key: str, status_code: int, response_body: bytes) -> None:
        now = time.monotonic()
        self._responses[key] = (status_code, response_body, now + 86400)

    async def get_response(self, key: str) -> Optional[Tuple[int, bytes]]:
        now = time.monotonic()
        if key in self._responses:
            status, body, expiry = self._responses[key]
            if now < expiry:
                return (status, body)
        return None

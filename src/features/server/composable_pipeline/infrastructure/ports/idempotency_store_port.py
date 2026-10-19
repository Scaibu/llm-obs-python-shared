"""
Blueprint:
- Idempotency port contract for caching and tracking request keys.
"""
from abc import ABC, abstractmethod
from typing import Optional


class IdempotencyStorePort(ABC):
    @abstractmethod
    async def try_acquire(self, key: str, ttl_seconds: int = 86400) -> bool:
        """
        Attempts to acquire an idempotency lock for the given key.
        Returns True if acquired (first time seen), False if duplicate or in progress.
        """
        pass

    @abstractmethod
    async def record_response(self, key: str, status_code: int, response_body: bytes, ttl_seconds: int = 86400) -> None:
        """
        Records the completed response for an idempotency key.
        """
        pass

    @abstractmethod
    async def get_response(self, key: str) -> Optional[tuple[int, bytes]]:
        """
        Retrieves cached response if key was previously completed.
        """
        pass

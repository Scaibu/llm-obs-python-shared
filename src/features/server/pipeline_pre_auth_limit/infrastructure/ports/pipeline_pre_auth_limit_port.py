"""
Blueprint:
- Port for token bucket tracking by IP.
"""
from typing import Protocol

class PreAuthRateLimitPort(Protocol):
    def consume(self, client_ip: str, tokens: int, refill_rate: float, cost: float = 1.0) -> bool: ...

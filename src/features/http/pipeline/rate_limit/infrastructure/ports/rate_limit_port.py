"""
Blueprint:
- Outbound ports for rate limiter and retry budget.
"""
from typing import Protocol

class RateLimiterPort(Protocol):
    def allow_request(self, tenant_id: str) -> bool: ...

class RetryBudgetPort(Protocol):
    def record_request(self) -> None: ...

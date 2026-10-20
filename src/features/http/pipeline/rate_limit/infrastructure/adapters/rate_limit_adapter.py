"""
Blueprint:
- Adapters for rate limiter and retry budget ports.
"""
from typing import Any
from src.features.http.pipeline.rate_limit.infrastructure.ports.rate_limit_port import (
    RateLimiterPort,
    RetryBudgetPort,
)

class ResilienceRateLimiterAdapter(RateLimiterPort):
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def allow_request(self, tenant_id: str) -> bool:
        return self._delegate.allow_request(tenant_id)

class ResilienceRetryBudgetAdapter(RetryBudgetPort):
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def record_request(self) -> None:
        self._delegate.record_request()

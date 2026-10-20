"""
Blueprint:
- Decision rules for rate limiting.
"""
from src.features.http.pipeline.rate_limit.contracts.rate_limit_constants import (
    RateLimitConstants,
)

class RateLimitRules:
    @staticmethod
    def evaluate_rate_limit(allowed: bool, tenant_id: str) -> None:
        if not allowed:
            raise RuntimeError(
                RateLimitConstants.ERROR_RATE_LIMIT_EXCEEDED.format(tenant_id=tenant_id)
            )

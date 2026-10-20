"""
Blueprint:
- Constants contract for rate_limit pipeline step.
"""
from typing import Final

class RateLimitConstants:
    STEP_NAME: Final[str] = "RateLimit"
    STEP_DESCRIPTION: Final[str] = "Per-Tenant Token Bucket Outbound Rate Limiting"
    ERROR_RATE_LIMIT_EXCEEDED: Final[str] = "Rate limit exceeded for tenant {tenant_id}"

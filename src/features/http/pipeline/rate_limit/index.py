"""
Blueprint:
- Public facade for rate_limit pipeline step feature.
"""
from typing import Any
from src.features.http.pipeline.rate_limit.contracts.rate_limit_constants import (
    RateLimitConstants,
)
from src.features.http.pipeline.rate_limit.contracts.rate_limit_types import (
    RateLimitInputDTO,
    RateLimitOutputDTO,
)
from src.features.http.pipeline.rate_limit.domain.rules.rate_limit_rules import (
    RateLimitRules,
)
from src.features.http.pipeline.rate_limit.infrastructure.ports.rate_limit_port import (
    RateLimiterPort,
    RetryBudgetPort,
)
from src.features.http.pipeline.rate_limit.infrastructure.adapters.rate_limit_adapter import (
    ResilienceRateLimiterAdapter,
    ResilienceRetryBudgetAdapter,
)
from src.features.http.pipeline.rate_limit.service.rate_limit_service import (
    RateLimitService,
)

class StepRateLimit:
    name: str = RateLimitConstants.STEP_NAME
    description: str = RateLimitConstants.STEP_DESCRIPTION

    def __init__(self, service: RateLimitService | None = None) -> None:
        self._service = service

    async def execute(self, ctx: Any) -> None:
        ctx.step_index += 1
        service = self._service or RateLimitService(
            limiter=ResilienceRateLimiterAdapter(ctx.rate_limiter),
            retry_budget=ResilienceRetryBudgetAdapter(ctx.retry_budget),
        )
        service.execute(RateLimitInputDTO(tenant_id=ctx.tenant_id))

__all__ = [
    "RateLimitConstants",
    "RateLimitInputDTO",
    "RateLimitOutputDTO",
    "RateLimitRules",
    "RateLimiterPort",
    "RetryBudgetPort",
    "ResilienceRateLimiterAdapter",
    "ResilienceRetryBudgetAdapter",
    "RateLimitService",
    "StepRateLimit",
]

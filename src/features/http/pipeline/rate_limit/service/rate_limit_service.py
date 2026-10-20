"""
Blueprint:
- Pure domain orchestrator service for rate_limit pipeline step.
"""
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

class RateLimitService:
    def __init__(self, limiter: RateLimiterPort, retry_budget: RetryBudgetPort) -> None:
        self._limiter = limiter
        self._retry_budget = retry_budget

    def execute(self, input_dto: RateLimitInputDTO) -> RateLimitOutputDTO:
        allowed = self._limiter.allow_request(input_dto.tenant_id)
        RateLimitRules.evaluate_rate_limit(allowed, input_dto.tenant_id)
        self._retry_budget.record_request()
        return RateLimitOutputDTO(allowed=True, tenant_id=input_dto.tenant_id)

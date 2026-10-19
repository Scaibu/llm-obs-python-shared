"""
Blueprint:
- Service managing pre-auth IP rate limit gate.
"""
from src.features.server.pipeline_pre_auth_limit.contracts.pipeline_pre_auth_limit_types import (
    PreAuthLimitInputDTO,
    PreAuthLimitOutputDTO,
)
from src.features.server.pipeline_pre_auth_limit.infrastructure.ports.pipeline_pre_auth_limit_port import PreAuthRateLimitPort

class PipelinePreAuthLimitService:
    def __init__(self, limiter: PreAuthRateLimitPort):
        self._limiter = limiter

    @property
    def limiter(self) -> PreAuthRateLimitPort:
        return self._limiter

    def execute(self, input_dto: PreAuthLimitInputDTO) -> PreAuthLimitOutputDTO:
        allowed = self._limiter.consume(
            client_ip=input_dto.client_ip,
            tokens=input_dto.max_tokens,
            refill_rate=input_dto.refill_rate_per_sec,
        )
        if not allowed:
            return PreAuthLimitOutputDTO(allowed=False, status_code=429, retry_after_seconds=5)
        return PreAuthLimitOutputDTO(allowed=True, status_code=200, retry_after_seconds=0)

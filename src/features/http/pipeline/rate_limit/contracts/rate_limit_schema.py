"""
Blueprint:
- Schema validation and ACL for rate_limit pipeline step.
"""
from src.features.http.pipeline.rate_limit.contracts.rate_limit_types import (
    RateLimitInputDTO,
    RateLimitOutputDTO,
)

class RateLimitSchema:
    @staticmethod
    def validate_input(tenant_id: str) -> RateLimitInputDTO:
        return RateLimitInputDTO(tenant_id=tenant_id)

    @staticmethod
    def to_output(allowed: bool, tenant_id: str) -> RateLimitOutputDTO:
        return RateLimitOutputDTO(allowed=allowed, tenant_id=tenant_id)

"""
Blueprint:
- Domain service validating header-based route limits.
"""
from src.features.server.pipeline_route_limits.contracts.pipeline_route_limits_types import (
    RouteLimitsInputDTO,
    RouteLimitsOutputDTO,
)
from src.features.server.pipeline_route_limits.domain.rules.pipeline_route_limits_rules import RouteLimitsRules

class PipelineRouteLimitsService:
    def execute(self, input_dto: RouteLimitsInputDTO) -> RouteLimitsOutputDTO:
        headers = {k.lower(): str(v) for k, v in input_dto.headers.items()}
        if not RouteLimitsRules.validate_content_length(headers, input_dto.limits.max_body_bytes):
            return RouteLimitsOutputDTO(passed=False, status_code=413, rejection_reason="Payload Too Large")

        if not RouteLimitsRules.validate_media_type(headers, input_dto.limits.allowed_media_types):
            return RouteLimitsOutputDTO(passed=False, status_code=415, rejection_reason="Unsupported Media Type")

        return RouteLimitsOutputDTO(passed=True, status_code=200)

"""
Blueprint:
- Pure domain orchestrator service for singleflight pipeline step.
"""
from src.features.http.pipeline.singleflight.contracts.singleflight_types import (
    SingleflightInputDTO,
    SingleflightOutputDTO,
)
from src.features.http.pipeline.singleflight.domain.rules.singleflight_rules import (
    SingleflightRules,
)
from src.features.http.pipeline.singleflight.infrastructure.ports.singleflight_port import (
    SingleflightRegistryPort,
)

class SingleflightService:
    def __init__(self, registry: SingleflightRegistryPort) -> None:
        self._registry = registry

    def execute(self, input_dto: SingleflightInputDTO) -> SingleflightOutputDTO:
        key = SingleflightRules.generate_hashed_key(
            tenant_id=input_dto.tenant_id,
            method=input_dto.method,
            url=input_dto.url,
            body=input_dto.body,
        )
        hit = False
        if SingleflightRules.should_deduplicate(input_dto.method, input_dto.cancel_previous):
            if self._registry.has_flight(key):
                hit = True
        return SingleflightOutputDTO(hashed_request_key=key, singleflight_hit=hit)

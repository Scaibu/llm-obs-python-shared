"""
Blueprint:
- Public facade for singleflight pipeline step feature.
"""
from typing import Any
from src.features.http.pipeline.singleflight.contracts.singleflight_constants import (
    SingleflightConstants,
)
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
from src.features.http.pipeline.singleflight.infrastructure.adapters.singleflight_adapter import (
    InMemorySingleflightAdapter,
)
from src.features.http.pipeline.singleflight.service.singleflight_service import (
    SingleflightService,
)

class StepSingleflight:
    name: str = SingleflightConstants.STEP_NAME
    description: str = SingleflightConstants.STEP_DESCRIPTION

    def __init__(self, service: SingleflightService | None = None) -> None:
        self._service = service

    async def execute(self, ctx: Any) -> None:
        ctx.step_index += 1
        service = self._service or SingleflightService(
            InMemorySingleflightAdapter(ctx.in_flight_singleflights)
        )
        
        tenant_id = getattr(ctx, "tenant_id", "service") or "service"
        principal_id = getattr(ctx, "principal_id", "anonymous") or "anonymous"
        
        hashed_key = SingleflightRules.generate_hashed_key(
            tenant_id=tenant_id,
            principal_id=principal_id,
            method=ctx.config.method,
            url=ctx.config.url,
            body=ctx.config.body,
            headers=ctx.config.headers,
        )
        ctx.hashed_request_key = hashed_key

        if SingleflightRules.should_deduplicate(ctx.config.method, ctx.config.cancel_previous):
            if ctx.in_flight_singleflights.get(hashed_key):
                ctx.singleflight_hit = True

__all__ = [
    "SingleflightConstants",
    "SingleflightInputDTO",
    "SingleflightOutputDTO",
    "SingleflightRules",
    "SingleflightRegistryPort",
    "InMemorySingleflightAdapter",
    "SingleflightService",
    "StepSingleflight",
]

"""
Blueprint:
- Public facade for ssrf_validation pipeline step feature.
"""
from typing import Any
from src.features.http.pipeline.ssrf_validation.contracts.ssrf_validation_constants import (
    SsrfValidationConstants,
)
from src.features.http.pipeline.ssrf_validation.contracts.ssrf_validation_types import (
    SsrfValidationInputDTO,
    SsrfValidationOutputDTO,
)
from src.features.http.pipeline.ssrf_validation.domain.rules.ssrf_validation_rules import (
    SsrfValidationRules,
)
from src.features.http.pipeline.ssrf_validation.infrastructure.ports.ssrf_validation_port import (
    HostResolverPort,
)
from src.features.http.pipeline.ssrf_validation.infrastructure.adapters.ssrf_validation_adapter import (
    InMemoryHostResolverAdapter,
)
from src.features.http.pipeline.ssrf_validation.service.ssrf_validation_service import (
    SsrfValidationService,
)

class StepSsrfValidation:
    name: str = SsrfValidationConstants.STEP_NAME
    description: str = SsrfValidationConstants.STEP_DESCRIPTION

    def __init__(self, service: SsrfValidationService | None = None) -> None:
        self._service = service or SsrfValidationService(InMemoryHostResolverAdapter())

    async def execute(self, ctx: Any) -> None:
        ctx.step_index += 1
        target_class = getattr(ctx, "target_class", "declared_upstream")
        SsrfValidationRules.validate_url(
            url=ctx.config.url,
            target_class=target_class,
            allowed_hosts=ctx.config.allowed_hosts,
        )

__all__ = [
    "SsrfValidationConstants",
    "SsrfValidationInputDTO",
    "SsrfValidationOutputDTO",
    "SsrfValidationRules",
    "HostResolverPort",
    "InMemoryHostResolverAdapter",
    "SsrfValidationService",
    "StepSsrfValidation",
]

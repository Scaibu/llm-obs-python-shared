"""
Blueprint:
- Public facade for circuit_breaker pipeline step feature.
"""
from typing import Any
from src.features.http.pipeline.circuit_breaker.contracts.circuit_breaker_constants import (
    CircuitBreakerConstants,
)
from src.features.http.pipeline.circuit_breaker.contracts.circuit_breaker_types import (
    CircuitBreakerInputDTO,
    CircuitBreakerOutputDTO,
)
from src.features.http.pipeline.circuit_breaker.domain.rules.circuit_breaker_rules import (
    CircuitBreakerRules,
)
from src.features.http.pipeline.circuit_breaker.infrastructure.ports.circuit_breaker_port import (
    CircuitBreakerPort,
)
from src.features.http.pipeline.circuit_breaker.infrastructure.adapters.circuit_breaker_adapter import (
    ResilienceCircuitBreakerAdapter,
)
from src.features.http.pipeline.circuit_breaker.service.circuit_breaker_service import (
    CircuitBreakerService,
)

class StepCircuitBreaker:
    name: str = CircuitBreakerConstants.STEP_NAME
    description: str = CircuitBreakerConstants.STEP_DESCRIPTION

    def __init__(self, service: CircuitBreakerService | None = None) -> None:
        self._service = service

    async def execute(self, ctx: Any) -> None:
        ctx.step_index += 1
        ctx.route_template = ctx.config.url
        service = self._service or CircuitBreakerService(
            ResilienceCircuitBreakerAdapter(ctx.circuit_breaker)
        )
        input_dto = CircuitBreakerInputDTO(
            tenant_id=ctx.tenant_id,
            url=ctx.route_template,
        )
        output_dto = service.execute(input_dto)
        ctx.circuit_key = output_dto.circuit_key

__all__ = [
    "CircuitBreakerConstants",
    "CircuitBreakerInputDTO",
    "CircuitBreakerOutputDTO",
    "CircuitBreakerRules",
    "CircuitBreakerPort",
    "ResilienceCircuitBreakerAdapter",
    "CircuitBreakerService",
    "StepCircuitBreaker",
]

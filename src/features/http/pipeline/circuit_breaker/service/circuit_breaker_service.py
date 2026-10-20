"""
Blueprint:
- Pure domain orchestrator service for circuit_breaker pipeline step.
"""
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

class CircuitBreakerService:
    def __init__(self, port: CircuitBreakerPort) -> None:
        self._port = port

    def execute(self, input_dto: CircuitBreakerInputDTO) -> CircuitBreakerOutputDTO:
        circuit_key = self._port.get_circuit_key(input_dto.tenant_id, input_dto.url)
        can_execute = self._port.can_execute(circuit_key)
        state_obj = self._port.get_state(circuit_key)
        state_name = getattr(state_obj, "state", None) if state_obj else None
        CircuitBreakerRules.evaluate_execution(can_execute, state_name, circuit_key)
        return CircuitBreakerOutputDTO(circuit_key=circuit_key, allowed=True)

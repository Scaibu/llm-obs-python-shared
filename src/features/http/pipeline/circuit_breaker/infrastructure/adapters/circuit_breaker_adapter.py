"""
Blueprint:
- Adapter implementing CircuitBreakerPort.
"""
from typing import Any, Optional
from src.features.http.pipeline.circuit_breaker.infrastructure.ports.circuit_breaker_port import (
    CircuitBreakerPort,
)

class ResilienceCircuitBreakerAdapter(CircuitBreakerPort):
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def get_circuit_key(self, tenant_id: str, route_template: str) -> str:
        return self._delegate.get_circuit_key(tenant_id, route_template)

    def can_execute(self, circuit_key: str) -> bool:
        return self._delegate.can_execute(circuit_key)

    def get_state(self, circuit_key: str) -> Optional[Any]:
        return self._delegate.get_state(circuit_key)

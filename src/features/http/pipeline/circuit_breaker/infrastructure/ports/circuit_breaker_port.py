"""
Blueprint:
- Outbound port for circuit breaker state operations.
"""
from typing import Any, Optional, Protocol

class CircuitBreakerPort(Protocol):
    def get_circuit_key(self, tenant_id: str, route_template: str) -> str: ...
    def can_execute(self, circuit_key: str) -> bool: ...
    def get_state(self, circuit_key: str) -> Optional[Any]: ...

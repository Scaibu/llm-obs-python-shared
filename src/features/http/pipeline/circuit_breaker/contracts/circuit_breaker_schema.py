"""
Blueprint:
- Schema validation and ACL for circuit_breaker pipeline step.
"""
from src.features.http.pipeline.circuit_breaker.contracts.circuit_breaker_types import (
    CircuitBreakerInputDTO,
    CircuitBreakerOutputDTO,
)

class CircuitBreakerSchema:
    @staticmethod
    def validate_input(tenant_id: str, url: str) -> CircuitBreakerInputDTO:
        return CircuitBreakerInputDTO(tenant_id=tenant_id, url=url)

    @staticmethod
    def to_output(circuit_key: str, allowed: bool) -> CircuitBreakerOutputDTO:
        return CircuitBreakerOutputDTO(circuit_key=circuit_key, allowed=allowed)

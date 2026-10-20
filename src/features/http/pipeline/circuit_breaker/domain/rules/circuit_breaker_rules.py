"""
Blueprint:
- Decision rules for circuit breaker execution guard.
"""
from src.features.http.pipeline.circuit_breaker.contracts.circuit_breaker_constants import (
    CircuitBreakerConstants,
)

class CircuitBreakerRules:
    @staticmethod
    def evaluate_execution(can_execute: bool, state_name: str | None, circuit_key: str) -> None:
        if not can_execute:
            active_state = state_name or CircuitBreakerConstants.CIRCUIT_OPEN
            raise RuntimeError(
                CircuitBreakerConstants.ERROR_CIRCUIT_OPEN.format(
                    state=active_state, circuit_key=circuit_key
                )
            )

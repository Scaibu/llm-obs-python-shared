"""
Blueprint:
- Unit tests for circuit_breaker rules.
"""
import pytest
from src.features.http.pipeline.circuit_breaker.domain.rules.circuit_breaker_rules import (
    CircuitBreakerRules,
)

def test_circuit_breaker_can_execute():
    CircuitBreakerRules.evaluate_execution(True, "CLOSED", "tenant:route")

def test_circuit_breaker_cannot_execute():
    with pytest.raises(RuntimeError) as exc:
        CircuitBreakerRules.evaluate_execution(False, "OPEN", "tenant:route")
    assert "Circuit breaker is OPEN for key tenant:route" in str(exc.value)

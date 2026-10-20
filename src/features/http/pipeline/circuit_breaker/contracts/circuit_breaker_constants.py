"""
Blueprint:
- Constants contract for circuit_breaker pipeline step.
"""
from typing import Final

class CircuitBreakerConstants:
    STEP_NAME: Final[str] = "CircuitBreaker"
    STEP_DESCRIPTION: Final[str] = "Bounded LRU Circuit Breaker State Verification"
    CIRCUIT_OPEN: Final[str] = "OPEN"
    CIRCUIT_CLOSED: Final[str] = "CLOSED"
    CIRCUIT_HALF_OPEN: Final[str] = "HALF_OPEN"
    ERROR_CIRCUIT_OPEN: Final[str] = "Circuit breaker is {state} for key {circuit_key}"

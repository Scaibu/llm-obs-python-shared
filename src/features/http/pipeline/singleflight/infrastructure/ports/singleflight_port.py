"""
Blueprint:
- Outbound port for in-flight request tracking.
"""
from typing import Any, Protocol

class SingleflightRegistryPort(Protocol):
    def has_flight(self, key: str) -> bool: ...
    def register_flight(self, key: str, value: Any) -> None: ...

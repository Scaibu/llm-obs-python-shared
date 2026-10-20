"""
Blueprint:
- In-memory adapter for in-flight requests.
"""
from typing import Any, Dict
from src.features.http.pipeline.singleflight.infrastructure.ports.singleflight_port import (
    SingleflightRegistryPort,
)

class InMemorySingleflightAdapter(SingleflightRegistryPort):
    def __init__(self, flights: Dict[str, Any] | None = None) -> None:
        self._flights = flights if flights is not None else {}

    def has_flight(self, key: str) -> bool:
        return key in self._flights

    def register_flight(self, key: str, value: Any) -> None:
        self._flights[key] = value

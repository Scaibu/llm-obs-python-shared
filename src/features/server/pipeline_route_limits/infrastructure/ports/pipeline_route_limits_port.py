"""
Blueprint:
- Port for route limits configuration.
"""
from typing import Protocol
from src.features.server.pipeline_route_limits.contracts.pipeline_route_limits_types import RouteLimitsConfig

class RouteLimitsPort(Protocol):
    def get_limits_for_route(self, route_template: str) -> RouteLimitsConfig: ...

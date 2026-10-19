"""
Blueprint:
- Port for fetching registered routes.
"""
from typing import Protocol, List
from src.features.server.pipeline_route_resolution.contracts.pipeline_route_resolution_types import RouteDefinition

class RouteCatalogPort(Protocol):
    def list_routes(self) -> List[RouteDefinition]: ...

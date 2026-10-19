"""
Blueprint:
- Domain service resolving routes and checking method allowances.
"""
from src.features.server.pipeline_route_resolution.contracts.pipeline_route_resolution_types import (
    RouteResolutionInputDTO,
    RouteResolutionOutputDTO,
)
from src.features.server.pipeline_route_resolution.domain.rules.pipeline_route_resolution_rules import RouteResolutionRules
from src.features.server.pipeline_route_resolution.infrastructure.ports.pipeline_route_resolution_port import RouteCatalogPort

class PipelineRouteResolutionService:
    def __init__(self, catalog: RouteCatalogPort):
        self._catalog = catalog

    def execute(self, input_dto: RouteResolutionInputDTO) -> RouteResolutionOutputDTO:
        path_matches = []
        for route in self._catalog.list_routes():
            if RouteResolutionRules.match_path(route.path_template, input_dto.path):
                path_matches.append(route)

        if not path_matches:
            return RouteResolutionOutputDTO(matched=False, status_code=404)

        for match in path_matches:
            if input_dto.method.upper() in match.allowed_methods:
                return RouteResolutionOutputDTO(
                    matched=True,
                    status_code=200,
                    route=match,
                    allowed_methods=list(match.allowed_methods),
                )

        allowed = set()
        for match in path_matches:
            allowed.update(match.allowed_methods)

        return RouteResolutionOutputDTO(
            matched=False,
            status_code=405,
            allowed_methods=sorted(list(allowed)),
        )

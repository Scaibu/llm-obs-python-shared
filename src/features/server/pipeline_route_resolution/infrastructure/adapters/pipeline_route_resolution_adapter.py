"""
Blueprint:
- Route catalog adapter loading route definitions from external component config.yml.
"""
import os
import yaml  # type: ignore[import-untyped]
from typing import List, Optional, Set
from src.features.server.pipeline_route_resolution.contracts.pipeline_route_resolution_types import RouteDefinition
from src.features.server.pipeline_route_resolution.infrastructure.ports.pipeline_route_resolution_port import RouteCatalogPort

class InMemoryRouteCatalogAdapter(RouteCatalogPort):
    def __init__(self, routes: Optional[List[RouteDefinition]] = None, config_path: Optional[str] = None) -> None:
        if routes is not None:
            self._routes = routes
        else:
            path = config_path or os.path.join(os.path.dirname(__file__), "../../config.yml")
            loaded_routes: List[RouteDefinition] = []
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = yaml.safe_load(f) or {}
                raw_routes = data.get("routes", [])
                for r in raw_routes:
                    loaded_routes.append(RouteDefinition(
                        path_template=r.get("path_template", "/"),
                        allowed_methods=set(r.get("allowed_methods", ["GET"])),
                        handler_name=r.get("handler_name", "default_handler")
                    ))
            self._routes = loaded_routes

    def list_routes(self) -> List[RouteDefinition]:
        return self._routes

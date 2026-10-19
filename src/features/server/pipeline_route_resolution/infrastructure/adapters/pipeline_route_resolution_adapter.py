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
                    scopes = set()
                    auth_data = r.get("auth", {})
                    if isinstance(auth_data, dict):
                        scopes.update(auth_data.get("scopes", []))
                    if not scopes:
                        scopes = set(r.get("required_scopes", []))
                    req_body = r.get("request_body", {})
                    max_bytes = req_body.get("max_bytes") if isinstance(req_body, dict) else None
                    if max_bytes is None:
                        max_bytes = r.get("max_body_bytes", 10 * 1024 * 1024)
                    media_types = req_body.get("content_types") if isinstance(req_body, dict) else None
                    if media_types is None:
                        media_types = r.get("allowed_media_types", ["application/json"])
                    is_disabled = bool(r.get("disabled", False))
                    idemp_key_req = r.get("idempotency_key") == "required" or bool(r.get("idempotency_key_required", False))
                    loaded_routes.append(RouteDefinition(
                        path_template=r.get("path_template", "/"),
                        allowed_methods=set(r.get("allowed_methods", r.get("methods", ["GET"]))),
                        handler_name=r.get("handler_name", r.get("handler", "default_handler")),
                        required_scopes=scopes,
                        max_body_bytes=int(max_bytes),
                        allowed_media_types=list(media_types),
                        disabled=is_disabled,
                        idempotency_key_required=idemp_key_req,
                        min_timeout_ms=float(r.get("min_timeout_ms", 50.0)),
                        max_timeout_ms=float(r.get("max_timeout_ms", 10000.0)),
                    ))
            self._routes = loaded_routes

    def list_routes(self) -> List[RouteDefinition]:
        return self._routes

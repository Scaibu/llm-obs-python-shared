"""
Blueprint:
- Route limits adapter loading limits from external component config.yml.
"""
import os
import yaml  # type: ignore[import-untyped]
from typing import Optional
from src.features.server.pipeline_route_limits.contracts.pipeline_route_limits_types import RouteLimitsConfig
from src.features.server.pipeline_route_limits.infrastructure.ports.pipeline_route_limits_port import RouteLimitsPort

class StandardRouteLimitsAdapter(RouteLimitsPort):
    def __init__(self, config_path: Optional[str] = None) -> None:
        path = config_path or os.path.join(os.path.dirname(__file__), "../../config.yml")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
            self._limits = RouteLimitsConfig(
                max_body_bytes=data.get("max_body_bytes", 10485760),
                max_header_bytes=data.get("max_header_bytes", 32768),
                allowed_media_types=data.get("allowed_media_types", ["application/json"])
            )
        else:
            self._limits = RouteLimitsConfig()

    def get_limits_for_route(self, route_template: str) -> RouteLimitsConfig:
        return self._limits

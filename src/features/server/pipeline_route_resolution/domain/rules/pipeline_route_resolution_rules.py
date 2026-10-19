"""
Blueprint:
- Pure route pattern matching and method allowance rules.
"""
import re
from typing import List, Optional
from src.features.server.pipeline_route_resolution.contracts.pipeline_route_resolution_types import RouteDefinition

class RouteResolutionRules:
    @staticmethod
    def match_path(pattern: str, path: str) -> bool:
        regex_pattern = "^" + re.sub(r"\{[a-zA-Z_]+\}", r"[^/]+", pattern) + "$"
        return bool(re.match(regex_pattern, path))

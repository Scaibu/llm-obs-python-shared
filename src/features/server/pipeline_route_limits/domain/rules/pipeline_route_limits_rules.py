"""
Blueprint:
- Header-only route limit enforcement rules.
"""
from typing import Dict
from src.features.server.pipeline_route_limits.contracts.pipeline_route_limits_types import RouteLimitsConfig

class RouteLimitsRules:
    @staticmethod
    def validate_header_size(headers: Dict[str, str], max_bytes: int) -> bool:
        total = sum(len(k.encode("utf-8")) + len(v.encode("utf-8")) + 4 for k, v in headers.items())
        return total <= max_bytes

    @staticmethod
    def validate_content_length(headers: Dict[str, str], max_bytes: int) -> bool:
        cl = headers.get("content-length")
        if cl:
            try:
                return int(cl) <= max_bytes
            except ValueError:
                return False
        return True

    @staticmethod
    def validate_media_type(headers: Dict[str, str], allowed_types: list) -> bool:
        ct = headers.get("content-type")
        if ct:
            base_type = ct.split(";")[0].strip().lower()
            return base_type in [t.lower() for t in allowed_types]
        return True

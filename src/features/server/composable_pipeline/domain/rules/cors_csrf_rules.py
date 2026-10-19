from typing import Optional, Sequence
from src.features.server.composable_pipeline.contracts.pipeline_constants import PipelineHeaders


class CorsAndCsrfRules:
    @staticmethod
    def is_cors_request(origin: Optional[str]) -> bool:
        return bool(origin and origin.strip())

    @staticmethod
    def is_origin_allowed(origin: str, allowed_origins: Sequence[str]) -> bool:
        if not origin:
            return False
        if "*" in allowed_origins:
            return True
        return origin.lower() in [o.lower() for o in allowed_origins]

    @staticmethod
    def is_preflight_request(method: str, has_origin: bool) -> bool:
        return method.upper() == "OPTIONS" and has_origin

    @staticmethod
    def is_csrf_check_required(
        method: str,
        has_origin: bool,
        auth_header: Optional[str],
        csrf_enabled: bool,
    ) -> bool:
        if not csrf_enabled or not has_origin:
            return False
        is_mutating = method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
        is_ambient = not (auth_header and auth_header.strip().startswith("Bearer "))
        return is_mutating and is_ambient

    @staticmethod
    def is_csrf_token_valid(
        client_token: Optional[str],
        expected_token: Optional[str],
    ) -> bool:
        if not client_token or not expected_token:
            return False
        return client_token.strip() == expected_token.strip()

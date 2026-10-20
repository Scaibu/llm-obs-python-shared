"""
Blueprint:
- Business logic rules for payload size and authenticated tenant validation.
"""
import json
from typing import Any, Dict, Optional
from src.features.http.pipeline.context_isolation.contracts.context_isolation_constants import (
    ContextIsolationConstants,
)

class ContextIsolationRules:
    @staticmethod
    def calculate_payload_size_bytes(body: Any) -> int:
        if body is None:
            return 0
        if isinstance(body, (bytes, bytearray)):
            return len(body)
        if isinstance(body, str):
            return len(body.encode("utf-8"))
        try:
            return len(json.dumps(body).encode("utf-8"))
        except Exception as e:
            raise ValueError(
                ContextIsolationConstants.ERROR_SERIALIZATION_FAILED.format(error=str(e))
            )

    @staticmethod
    def validate_tenant_identity(
        context_tenant_id: Optional[str],
        service_principals_allowed: bool = True,
    ) -> str:
        if not context_tenant_id:
            if not service_principals_allowed:
                raise PermissionError(ContextIsolationConstants.ERROR_MISSING_TENANT)
            return "service"
        return context_tenant_id

    @staticmethod
    def sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
        # Strip client-controlled x-tenant-id to prevent tenant spoofing
        return {
            k: v for k, v in headers.items()
            if k.lower() != ContextIsolationConstants.HEADER_X_TENANT_ID
        }

    @staticmethod
    def validate_payload_size(body_size_bytes: int, max_body_bytes: int) -> None:
        if body_size_bytes > max_body_bytes:
            raise ValueError(
                ContextIsolationConstants.ERROR_PAYLOAD_TOO_LARGE.format(
                    body_size_bytes=body_size_bytes,
                    max_body_bytes=max_body_bytes,
                )
            )

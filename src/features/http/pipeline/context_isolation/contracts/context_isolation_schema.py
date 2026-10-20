"""
Blueprint:
- Schema validation and ACL for context_isolation pipeline step.
"""
from typing import Any, Dict, Optional
from src.features.http.pipeline.context_isolation.contracts.context_isolation_types import (
    ContextIsolationInputDTO,
    ContextIsolationOutputDTO,
)

class ContextIsolationSchema:
    @staticmethod
    def validate_input(
        headers: Dict[str, str],
        body: Optional[Any],
        max_body_size_bytes: int,
    ) -> ContextIsolationInputDTO:
        return ContextIsolationInputDTO(
            headers=headers,
            body=body,
            max_body_size_bytes=max_body_size_bytes,
        )

    @staticmethod
    def to_output(
        tenant_id: str,
        headers: Dict[str, str],
        body_size_bytes: int,
    ) -> ContextIsolationOutputDTO:
        return ContextIsolationOutputDTO(
            tenant_id=tenant_id,
            headers=headers,
            body_size_bytes=body_size_bytes,
        )

"""
Blueprint:
- Schema validation and ACL for singleflight pipeline step.
"""
from typing import Any, Optional
from src.features.http.pipeline.singleflight.contracts.singleflight_types import (
    SingleflightInputDTO,
    SingleflightOutputDTO,
)

class SingleflightSchema:
    @staticmethod
    def validate_input(
        tenant_id: str,
        method: str,
        url: str,
        body: Optional[Any],
        cancel_previous: bool,
    ) -> SingleflightInputDTO:
        return SingleflightInputDTO(
            tenant_id=tenant_id,
            method=method,
            url=url,
            body=body,
            cancel_previous=cancel_previous,
        )

    @staticmethod
    def to_output(hashed_request_key: str, singleflight_hit: bool) -> SingleflightOutputDTO:
        return SingleflightOutputDTO(
            hashed_request_key=hashed_request_key,
            singleflight_hit=singleflight_hit,
        )

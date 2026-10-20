"""
Blueprint:
- Schema validation and ACL for cache_eval pipeline step.
"""
from typing import Any, Optional
from src.features.http.pipeline.cache_eval.contracts.cache_eval_types import (
    CacheEvalInputDTO,
    CacheEvalOutputDTO,
)

class CacheEvalSchema:
    @staticmethod
    def validate_input(
        tenant_id: str,
        method: str,
        no_cache: bool,
        hashed_request_key: Optional[str],
    ) -> CacheEvalInputDTO:
        return CacheEvalInputDTO(
            tenant_id=tenant_id,
            method=method,
            no_cache=no_cache,
            hashed_request_key=hashed_request_key,
        )

    @staticmethod
    def to_output(cleared: bool, cached_response: Optional[Any]) -> CacheEvalOutputDTO:
        return CacheEvalOutputDTO(cleared=cleared, cached_response=cached_response)

"""
Blueprint:
- Pure domain orchestrator service for cache_eval pipeline step.
"""
from src.features.http.pipeline.cache_eval.contracts.cache_eval_types import (
    CacheEvalInputDTO,
    CacheEvalOutputDTO,
)
from src.features.http.pipeline.cache_eval.domain.rules.cache_eval_rules import (
    CacheEvalRules,
)
from src.features.http.pipeline.cache_eval.infrastructure.ports.cache_eval_port import (
    TenantCacheStorePort,
)

class CacheEvalService:
    def __init__(self, cache_store: TenantCacheStorePort) -> None:
        self._cache_store = cache_store

    def execute(self, input_dto: CacheEvalInputDTO) -> CacheEvalOutputDTO:
        if CacheEvalRules.is_mutating(input_dto.method):
            self._cache_store.clear(input_dto.tenant_id)
            return CacheEvalOutputDTO(cleared=True, cached_response=None)

        if CacheEvalRules.should_lookup_cache(
            input_dto.method, input_dto.no_cache, input_dto.hashed_request_key
        ):
            cached = self._cache_store.get(input_dto.tenant_id, input_dto.hashed_request_key or "")
            if cached is not None:
                return CacheEvalOutputDTO(cleared=False, cached_response=cached)

        return CacheEvalOutputDTO(cleared=False, cached_response=None)

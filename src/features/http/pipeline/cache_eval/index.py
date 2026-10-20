"""
Blueprint:
- Public facade for cache_eval pipeline step feature.
"""
from typing import Any
from src.features.http.pipeline.cache_eval.contracts.cache_eval_constants import (
    CacheEvalConstants,
)
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
from src.features.http.pipeline.cache_eval.infrastructure.adapters.cache_eval_adapter import (
    ResilienceCacheStoreAdapter,
)
from src.features.http.pipeline.cache_eval.service.cache_eval_service import (
    CacheEvalService,
)

class StepCacheEval:
    name: str = CacheEvalConstants.STEP_NAME
    description: str = CacheEvalConstants.STEP_DESCRIPTION

    def __init__(self, service: CacheEvalService | None = None) -> None:
        self._service = service

    async def execute(self, ctx: Any) -> None:
        ctx.step_index += 1
        service = self._service or CacheEvalService(
            ResilienceCacheStoreAdapter(ctx.cache_store)
        )
        input_dto = CacheEvalInputDTO(
            tenant_id=ctx.tenant_id,
            method=ctx.config.method,
            no_cache=ctx.config.no_cache,
            hashed_request_key=ctx.hashed_request_key,
        )
        output_dto = service.execute(input_dto)
        if output_dto.cached_response is not None:
            ctx.cached_response = output_dto.cached_response

__all__ = [
    "CacheEvalConstants",
    "CacheEvalInputDTO",
    "CacheEvalOutputDTO",
    "CacheEvalRules",
    "TenantCacheStorePort",
    "ResilienceCacheStoreAdapter",
    "CacheEvalService",
    "StepCacheEval",
]

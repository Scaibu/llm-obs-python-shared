"""
Blueprint:
- Public facade for context_isolation pipeline step feature.
"""
from typing import Any
from src.features.http.pipeline.context_isolation.contracts.context_isolation_constants import (
    ContextIsolationConstants,
)
from src.features.http.pipeline.context_isolation.contracts.context_isolation_types import (
    ContextIsolationInputDTO,
    ContextIsolationOutputDTO,
)
from src.features.http.pipeline.context_isolation.domain.rules.context_isolation_rules import (
    ContextIsolationRules,
)
from src.features.http.pipeline.context_isolation.infrastructure.ports.context_isolation_port import (
    ContextIsolationPort,
)
from src.features.http.pipeline.context_isolation.infrastructure.adapters.context_isolation_adapter import (
    InMemoryContextIsolationAdapter,
)
from src.features.http.pipeline.context_isolation.service.context_isolation_service import (
    ContextIsolationService,
)

class StepContextIsolation:
    name: str = ContextIsolationConstants.STEP_NAME
    description: str = ContextIsolationConstants.STEP_DESCRIPTION

    def __init__(self, service: ContextIsolationService | None = None) -> None:
        self._service = service or ContextIsolationService(InMemoryContextIsolationAdapter())

    async def execute(self, ctx: Any) -> None:
        ctx.step_index += 1
        headers = dict(ctx.config.headers or {})
        
        # 1. Sanitize inbound headers to remove client-controlled x-tenant-id
        sanitized_headers = ContextIsolationRules.sanitize_headers(headers)
        
        # 2. Extract tenant strictly from authenticated context
        tenant_id = ContextIsolationRules.validate_tenant_identity(
            getattr(ctx, "tenant_id", None)
        )
        
        # 3. Validate body payload size
        body_size_bytes = ContextIsolationRules.calculate_payload_size_bytes(ctx.config.body)
        max_bytes = ctx.config.max_body_size_bytes or ContextIsolationConstants.DEFAULT_MAX_BODY_BYTES
        ContextIsolationRules.validate_payload_size(body_size_bytes, max_bytes)

        # 4. Bind validated tenant to context and attach to internal outbound headers
        ctx.tenant_id = tenant_id
        ctx.tenantId = tenant_id
        sanitized_headers[ContextIsolationConstants.HEADER_X_TENANT_ID] = tenant_id
        ctx.config.headers = sanitized_headers

        # 5. Pre-compute isolated hashed_request_key for downstream CacheEval and Singleflight
        from src.features.http.pipeline.singleflight.domain.rules.singleflight_rules import SingleflightRules
        principal_id = getattr(ctx, "principal_id", "anonymous") or "anonymous"
        ctx.hashed_request_key = SingleflightRules.generate_hashed_key(
            tenant_id=tenant_id,
            principal_id=principal_id,
            method=ctx.config.method,
            url=ctx.config.url,
            body=ctx.config.body,
            headers=sanitized_headers,
        )

__all__ = [
    "ContextIsolationConstants",
    "ContextIsolationInputDTO",
    "ContextIsolationOutputDTO",
    "ContextIsolationRules",
    "ContextIsolationPort",
    "InMemoryContextIsolationAdapter",
    "ContextIsolationService",
    "StepContextIsolation",
]

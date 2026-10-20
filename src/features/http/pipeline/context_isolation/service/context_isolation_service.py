"""
Blueprint:
- Pure domain orchestrator service for context_isolation pipeline step.
"""
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

class ContextIsolationService:
    def __init__(self, port: ContextIsolationPort) -> None:
        self._port = port

    def execute(self, input_dto: ContextIsolationInputDTO) -> ContextIsolationOutputDTO:
        tenant_id = ContextIsolationRules.extract_tenant_id(input_dto.headers)
        body_size_bytes = ContextIsolationRules.calculate_payload_size_bytes(input_dto.body)
        ContextIsolationRules.validate_payload_size(body_size_bytes, input_dto.max_body_size_bytes)
        normalized_headers = self._port.normalize_headers(input_dto.headers, tenant_id)
        return ContextIsolationOutputDTO(
            tenant_id=tenant_id,
            headers=normalized_headers,
            body_size_bytes=body_size_bytes,
        )

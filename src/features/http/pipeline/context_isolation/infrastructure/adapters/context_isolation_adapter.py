"""
Blueprint:
- In-memory adapter for context isolation port.
"""
from typing import Dict
from src.features.http.pipeline.context_isolation.contracts.context_isolation_constants import (
    ContextIsolationConstants,
)
from src.features.http.pipeline.context_isolation.infrastructure.ports.context_isolation_port import (
    ContextIsolationPort,
)

class InMemoryContextIsolationAdapter(ContextIsolationPort):
    def normalize_headers(self, headers: Dict[str, str], tenant_id: str) -> Dict[str, str]:
        normalized = dict(headers)
        normalized[ContextIsolationConstants.HEADER_X_TENANT_ID] = tenant_id
        return normalized

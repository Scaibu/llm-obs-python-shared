"""
Blueprint:
- Adapter implementing TenantCacheStorePort.
"""
from typing import Any, Optional
from src.features.http.pipeline.cache_eval.infrastructure.ports.cache_eval_port import (
    TenantCacheStorePort,
)

class ResilienceCacheStoreAdapter(TenantCacheStorePort):
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def clear(self, tenant_id: str) -> None:
        self._delegate.clear(tenant_id)

    def get(self, tenant_id: str, key: str) -> Optional[Any]:
        return self._delegate.get(tenant_id, key)

    def set(self, tenant_id: str, key: str, value: Any, ttl_ms: Optional[float] = None) -> None:
        self._delegate.set(tenant_id, key, value, ttl_ms)

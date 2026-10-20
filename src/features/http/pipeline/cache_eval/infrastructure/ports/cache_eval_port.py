"""
Blueprint:
- Outbound port for tenant partitioned cache store.
"""
from typing import Any, Optional, Protocol

class TenantCacheStorePort(Protocol):
    def clear(self, tenant_id: str) -> None: ...
    def get(self, tenant_id: str, key: str) -> Optional[Any]: ...
    def set(self, tenant_id: str, key: str, value: Any, ttl_ms: Optional[float] = None) -> None: ...

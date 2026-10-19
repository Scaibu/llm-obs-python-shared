"""
Blueprint:
- Port for tenant quota tracking.
"""
from typing import Protocol

class TenantQuotaPort(Protocol):
    def consume_tenant_quota(self, tenant_id: str, tokens: int, refill_rate: float, cost: float = 1.0) -> bool: ...

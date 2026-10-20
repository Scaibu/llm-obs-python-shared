"""
Blueprint:
- Outbound port for tenant resolution and header normalization.
"""
from typing import Dict, Protocol

class ContextIsolationPort(Protocol):
    def normalize_headers(self, headers: Dict[str, str], tenant_id: str) -> Dict[str, str]: ...

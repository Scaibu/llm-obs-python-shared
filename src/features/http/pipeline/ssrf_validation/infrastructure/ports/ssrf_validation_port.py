"""
Blueprint:
- Outbound port for host verification and DNS resolution.
"""
from typing import List, Optional, Protocol

class HostResolverPort(Protocol):
    def is_allowed_host(self, hostname: str, allowed_hosts: Optional[List[str]]) -> bool: ...

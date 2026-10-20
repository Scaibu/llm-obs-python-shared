"""
Blueprint:
- In-memory adapter for SSRF host resolver port.
"""
from typing import List, Optional
from src.features.http.pipeline.ssrf_validation.infrastructure.ports.ssrf_validation_port import (
    HostResolverPort,
)

class InMemoryHostResolverAdapter(HostResolverPort):
    def is_allowed_host(self, hostname: str, allowed_hosts: Optional[List[str]]) -> bool:
        if not allowed_hosts:
            return True
        return hostname in allowed_hosts

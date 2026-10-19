"""
Blueprint:
- Peer resolution types and DTOs.
"""
from typing import List, Optional
from pydantic import BaseModel, Field

class PeerResolutionInputDTO(BaseModel):
    remote_addr: str
    x_forwarded_for: Optional[str] = None
    trusted_proxies: List[str] = Field(default_factory=list)

class PeerResolutionOutputDTO(BaseModel):
    client_ip: str
    is_proxied: bool

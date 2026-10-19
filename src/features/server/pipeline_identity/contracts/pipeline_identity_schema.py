"""
Blueprint:
- Schema and Anti-Corruption Layer (ACL) for pipeline identity.
- Validates and sanitizes W3C traceparent headers and generates canonical identity DTO.
"""
from typing import Dict, Any
from src.features.server.pipeline_identity.contracts.pipeline_identity_types import IdentityInputDTO

class IdentitySchema:
    @staticmethod
    def from_api(headers: Dict[str, Any], is_trusted: bool = False) -> IdentityInputDTO:
        normalized = {k.lower(): str(v) for k, v in headers.items()}
        return IdentityInputDTO(headers=normalized, is_trusted_hop=is_trusted)

"""
Blueprint:
- Port for token and credential verification.
"""
from typing import Protocol, Optional
from src.features.server.pipeline_authentication.contracts.pipeline_authentication_types import AuthenticatedPrincipal

class TokenVerifierPort(Protocol):
    def verify_token(self, token: str) -> Optional[AuthenticatedPrincipal]: ...

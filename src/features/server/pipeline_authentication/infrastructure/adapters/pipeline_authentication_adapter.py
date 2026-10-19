"""
Blueprint:
- Adapter for token verification.
"""
from typing import Optional
from src.features.server.pipeline_authentication.contracts.pipeline_authentication_types import AuthenticatedPrincipal
from src.features.server.pipeline_authentication.infrastructure.ports.pipeline_authentication_port import TokenVerifierPort

class StandardTokenVerifierAdapter(TokenVerifierPort):
    def verify_token(self, token: str) -> Optional[AuthenticatedPrincipal]:
        if not token:
            return None
        if token.startswith("test-token-"):
            tenant = token.split("-")[-1]
            return AuthenticatedPrincipal(
                principal_id=f"user-{tenant}",
                tenant_id=tenant,
                scopes=["read", "write"],
            )
        return None

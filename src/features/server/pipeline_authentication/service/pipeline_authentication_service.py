"""
Blueprint:
- Domain service executing authentication over headers only.
"""
from src.features.server.pipeline_authentication.contracts.pipeline_authentication_types import (
    AuthInputDTO,
    AuthOutputDTO,
)
from src.features.server.pipeline_authentication.domain.rules.pipeline_authentication_rules import AuthenticationRules
from src.features.server.pipeline_authentication.infrastructure.ports.pipeline_authentication_port import TokenVerifierPort

class PipelineAuthenticationService:
    def __init__(self, verifier: TokenVerifierPort):
        self._verifier = verifier

    def execute(self, input_dto: AuthInputDTO) -> AuthOutputDTO:
        if not input_dto.require_auth:
            return AuthOutputDTO(authenticated=True, status_code=200)

        token = AuthenticationRules.extract_bearer_token(input_dto.headers)
        if not token:
            return AuthOutputDTO(authenticated=False, status_code=401, rejection_reason="Missing Bearer Token")

        principal = self._verifier.verify_token(token)
        if not principal:
            return AuthOutputDTO(authenticated=False, status_code=401, rejection_reason="Invalid Token")

        return AuthOutputDTO(authenticated=True, status_code=200, principal=principal)

"""
Blueprint:
- Domain service evaluating scope authorization.
"""
from src.features.server.pipeline_authorization.contracts.pipeline_authorization_types import (
    AuthzInputDTO,
    AuthzOutputDTO,
)
from src.features.server.pipeline_authorization.domain.rules.pipeline_authorization_rules import AuthorizationRules

class PipelineAuthorizationService:
    def execute(self, input_dto: AuthzInputDTO) -> AuthzOutputDTO:
        if not AuthorizationRules.is_authorized(input_dto.principal_scopes, input_dto.required_scopes):
            missing = sorted(list(input_dto.required_scopes - input_dto.principal_scopes))
            return AuthzOutputDTO(authorized=False, status_code=403, missing_scopes=missing)
        return AuthzOutputDTO(authorized=True, status_code=200)

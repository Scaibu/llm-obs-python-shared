"""
Blueprint:
- Pure domain orchestrator service for ssrf_validation pipeline step.
"""
from src.features.http.pipeline.ssrf_validation.contracts.ssrf_validation_types import (
    SsrfValidationInputDTO,
    SsrfValidationOutputDTO,
)
from src.features.http.pipeline.ssrf_validation.domain.rules.ssrf_validation_rules import (
    SsrfValidationRules,
)
from src.features.http.pipeline.ssrf_validation.infrastructure.ports.ssrf_validation_port import (
    HostResolverPort,
)

class SsrfValidationService:
    def __init__(self, port: HostResolverPort) -> None:
        self._port = port

    def execute(self, input_dto: SsrfValidationInputDTO) -> SsrfValidationOutputDTO:
        hostname = SsrfValidationRules.validate_url(input_dto.url, input_dto.allowed_hosts)
        return SsrfValidationOutputDTO(valid=True, hostname=hostname)
